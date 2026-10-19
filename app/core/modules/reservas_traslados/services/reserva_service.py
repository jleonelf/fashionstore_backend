"""Controller ReservaService — CU08/CU10/CU24 (RF09-RF12).

Contratos:
  Presentacion confirmarReserva()/cancelarReserva()/consultarReserva()
  Controller crear()/cancelar()/obtener() (+ preparar/atender en Entrega 4,
    expirarVencidas() para el job CU24)
  Datos ReservaRepository.crear()/actualizarEstado(),
    InventarioRepository.moverDisponibleAReservado()/liberarReservado(),
    MovimientoRepository.registrar(tipo=RESERVA/LIBERACION_RESERVA)

Toda mutacion de inventario corre en una unica transaccion de servicio con
SELECT FOR UPDATE en orden determinista y revalidacion posterior.
Los repositorios hacen flush; solo el servicio confirma o revierte.
"""
import secrets
import string
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.idempotencia import hash_payload, resolver_idempotencia
from backend.app.core.permisos import es_admin, exigir_sucursal
from backend.app.core.reloj import RelojSistema, asegurar_utc, calcular_vencimiento, entrada_local_a_utc
from backend.app.core.modules.reservas_traslados.models import DetalleReserva, Reserva, DetalleTraslado, Traslado
from backend.app.core.modules.inventario.models import MovimientoInventario
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.inventario.repositories.inventario_repository import InventarioRepository
from backend.app.core.modules.inventario.repositories.movimiento_repository import MovimientoRepository
from backend.app.core.modules.reservas_traslados.repositories.traslado_repository import TrasladoRepository
from backend.app.core.modules.reservas_traslados.repositories.reserva_repository import (
    ESTADOS_NO_TERMINALES_RESERVA,
    ReservaRepository,
)
from backend.app.core.modules.organizacion.repositories.sucursal_repository import SucursalRepository
from backend.app.core.modules.catalogo.repositories.variante_repository import VarianteRepository
from backend.app.core.modules.reservas_traslados.schemas import ExpiracionResultadoDTO, ReservaCrearDTO, ReservaDTO

CODIGO_ALFABETO = string.ascii_uppercase + string.digits
ESTADOS_CANCELABLES = ("PENDIENTE_TRASLADO", "PENDIENTE", "PREPARADA")
ADVISORY_LOCK_EXPRIACION = "fashionstore_expiracion_reservas"


class ReservaService:
    def __init__(self, db: AsyncSession, reloj=None):
        self.db = db
        self.reloj = reloj or RelojSistema()
        self.reserva_repo = ReservaRepository(db)
        self.inventario_repo = InventarioRepository(db)
        self.movimiento_repo = MovimientoRepository(db)
        self.traslado_repo = TrasladoRepository(db)
        self.sucursal_repo = SucursalRepository(db)
        self.variante_repo = VarianteRepository(db)

    # ---------------- creación (CU08) ----------------
    def _generar_codigo(self) -> str:
        return "FS-" + "".join(secrets.choice(CODIGO_ALFABETO) for _ in range(6))

    async def _codigo_unico(self) -> str:
        for _ in range(5):
            codigo = self._generar_codigo()
            if not await self.reserva_repo.existeCodigo(codigo):
                return codigo
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar un codigo de reserva unico",
        )

    async def crear(
        self, cliente: Usuario, dto: ReservaCrearDTO, clave: uuid.UUID
    ) -> Tuple[ReservaDTO, bool]:
        """Confirma una bolsa de forma atomica. Retorna (reserva, fue_creada).

        Idempotencia: misma clave + mismo payload -> original (fue_creada=False);
        misma clave + otro payload -> 409. Bajo concurrencia, el UNIQUE de
        clave_idempotencia serializa el intento logico duplicado.
        """
        carga = dto.model_dump(mode="json")
        digest = hash_payload(carga)
        # La sesion se comparte con get_usuario_actual (SELECT previo con
        # autobegin): no usar begin() explicito; patron commit/rollback
        # como RecepcionService.registrarLote().
        try:
            reintento = await resolver_idempotencia(self.db, Reserva, clave, digest)
            if reintento is not None:
                return await self._a_dto(reintento.id), False
            reserva = await self._crear_en_tx(cliente, dto, clave, digest)
            salida = await self._a_dto(reserva.id)
            await self.db.commit()
            return salida, True
        except IntegrityError as e:
            await self.db.rollback()
            mensaje = str(getattr(e, "orig", e))
            if "clave_idempotencia" in mensaje:
                existente = await self.reserva_repo.buscarPorClave(clave)
                if existente is None:  # pragma: no cover (condicion de carrera extrema)
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Conflicto concurrente de idempotencia",
                    )
                if existente.hash_solicitud != digest:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Idempotency-Key ya usada con otra solicitud",
                    )
                return await self._a_dto(existente.id), False
            raise
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise

    async def _crear_en_tx(
        self, cliente: Usuario, dto: ReservaCrearDTO, clave: uuid.UUID, digest: str
    ) -> Reserva:
        # 1. Validaciones de dominio (400/404), sin efectos aun.
        if not dto.lineas:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La reserva requiere al menos una linea")
        vistos = set()
        for linea in dto.lineas:
            if linea.cantidad <= 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cantidad solicitada debe ser mayor a cero")
            if linea.variante_id in vistos:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Variante duplicada en la reserva (una linea por variante)",
                )
            vistos.add(linea.variante_id)
            if linea.sucursal_origen_id is not None and linea.sucursal_origen_id == dto.sucursal_destino_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La sucursal origen del traslado debe ser distinta del destino",
                )
        destino = await self.sucursal_repo.buscarPorId(dto.sucursal_destino_id)
        if destino is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal destino no encontrada")
        if not destino.activa:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sucursal destino inactiva")
        variantes: Dict[uuid.UUID, object] = {}
        for linea in dto.lineas:
            variante = await self.variante_repo.buscarPorId(linea.variante_id)
            if variante is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Variante {linea.variante_id} no encontrada",
                )
            if not variante.activa:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Variante {variante.sku} inactiva",
                )
            variantes[linea.variante_id] = variante
            if linea.sucursal_origen_id is not None:
                origen = await self.sucursal_repo.buscarPorId(linea.sucursal_origen_id)
                if origen is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal origen no encontrada")
                if not origen.activa:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sucursal origen inactiva")

        # 2. Bloqueo pesimista en orden determinista (destino + origenes).
        claves = [(dto.sucursal_destino_id, l.variante_id) for l in dto.lineas]
        claves += [
            (l.sucursal_origen_id, l.variante_id)
            for l in dto.lineas
            if l.sucursal_origen_id is not None
        ]
        filas = await self.inventario_repo.bloquearFilas(claves)

        # 3. Decision atomica por linea con stock revalidado.
        ahora = self.reloj.ahora()
        planes = []  # (linea_dto, modo, cantidad) modo in {"LOCAL", "TRASLADO"}
        for linea in dto.lineas:
            destino_row = filas.get((dto.sucursal_destino_id, linea.variante_id))
            disponible_destino = destino_row.disponible if destino_row else 0
            if disponible_destino >= linea.cantidad:
                planes.append((linea, "LOCAL", linea.cantidad))
                continue
            if linea.sucursal_origen_id is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Sin stock local para {variantes[linea.variante_id].sku}: indique sucursal_origen_id o reduzca la cantidad",
                )
            origen_row = filas.get((linea.sucursal_origen_id, linea.variante_id))
            disponible_origen = origen_row.disponible if origen_row else 0
            if disponible_origen < linea.cantidad:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Sin stock suficiente en origen para {variantes[linea.variante_id].sku}",
                )
            planes.append((linea, "TRASLADO", linea.cantidad))
        # Si alguna linea no tuvo solucion se levanto 409 y nada se persiste.

        # 4. Cabecera + lineas + movimientos + traslados en la misma transaccion.
        con_traslado = any(modo == "TRASLADO" for _, modo, _ in planes)
        reserva = Reserva(
            cliente_id=cliente.id,
            sucursal_destino_id=dto.sucursal_destino_id,
            codigo=await self._codigo_unico(),
            estado="PENDIENTE_TRASLADO" if con_traslado else "PENDIENTE",
            fecha_creacion=ahora,
            fecha_visita=(entrada_local_a_utc(dto.fecha_visita) if dto.fecha_visita else None),
            vence_en=(
                entrada_local_a_utc(dto.fecha_visita) + timedelta(days=1)
                if dto.fecha_visita
                else calcular_vencimiento(ahora, False)
            ),
            observacion=dto.observacion,
            clave_idempotencia=clave,
            hash_solicitud=digest,
        )
        await self.reserva_repo.crear(reserva)
        for linea, modo, cantidad in planes:
            detalle = DetalleReserva(
                reserva_id=reserva.id,
                variante_id=linea.variante_id,
                cantidad_solicitada=linea.cantidad,
                cantidad_reservada=cantidad if modo == "LOCAL" else 0,
                cantidad_pendiente_traslado=cantidad if modo == "TRASLADO" else 0,
                cantidad_vendida=0,
                cantidad_liberada=0,
                estado_linea="RESERVADA" if modo == "LOCAL" else "PENDIENTE_TRASLADO",
            )
            self.db.add(detalle)
            await self.db.flush()
            if modo == "LOCAL":
                fila = filas[(dto.sucursal_destino_id, linea.variante_id)]
                fila.disponible -= cantidad
                fila.reservado += cantidad
                await self.db.flush()
                await self.movimiento_repo.registrar(
                    MovimientoInventario(
                        variante_id=linea.variante_id,
                        sucursal_destino_id=dto.sucursal_destino_id,
                        tipo="RESERVA",
                        cantidad=cantidad,
                        costo_unitario=Decimal(str(variantes[linea.variante_id].costo_promedio or 0)),
                        referencia_tipo="RESERVA",
                        referencia_id=reserva.id,
                        linea_referencia_id=detalle.id,
                        observacion=f"Reserva {reserva.codigo}",
                    )
                )
            else:
                traslado = Traslado(
                    reserva_id=reserva.id,
                    sucursal_origen_id=linea.sucursal_origen_id,
                    sucursal_destino_id=dto.sucursal_destino_id,
                    estado="SOLICITADO",
                    solicitado_por_id=cliente.id,
                )
                await self.traslado_repo.crear(traslado)
                self.db.add(
                    DetalleTraslado(
                        traslado_id=traslado.id,
                        detalle_reserva_id=detalle.id,
                        variante_id=linea.variante_id,
                        cantidad=cantidad,
                    )
                )
                await self.db.flush()
        return reserva

    # ---------------- consulta (CU08) ----------------
    async def _a_dto(self, reserva_id: uuid.UUID) -> ReservaDTO:
        from backend.app.core.modules.reservas_traslados.schemas import DetalleReservaDTO, TrasladoResumenDTO

        reserva = await self.reserva_repo.buscarPorId(reserva_id)
        if reserva is None:  # pragma: no cover (defensivo)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
        traslados = await self.reserva_repo.trasladosDeReserva(reserva.id)
        estado = reserva.estado
        if not isinstance(estado, str):
            estado = estado.name
        return ReservaDTO(
            id=reserva.id,
            cliente_id=reserva.cliente_id,
            sucursal_destino_id=reserva.sucursal_destino_id,
            codigo=reserva.codigo,
            estado=estado,
            fecha_creacion=reserva.fecha_creacion,
            fecha_visita=reserva.fecha_visita,
            vence_en=reserva.vence_en,
            observacion=reserva.observacion,
            adelanto_modalidad=reserva.adelanto_modalidad,
            adelanto_valor=reserva.adelanto_valor,
            adelanto_monto=reserva.adelanto_monto,
            preparada_en=reserva.preparada_en,
            atendida_en=reserva.atendida_en,
            preparada_por=reserva.preparada_por,
            atendida_por=reserva.atendida_por,
            detalles=[DetalleReservaDTO.model_validate(d) for d in reserva.detalles],
            traslados=[
                TrasladoResumenDTO(
                    id=t.id,
                    sucursal_origen_id=t.sucursal_origen_id,
                    sucursal_destino_id=t.sucursal_destino_id,
                    estado=t.estado if isinstance(t.estado, str) else t.estado.name,
                )
                for t in traslados
            ],
        )

    def _autorizar_lectura(self, usuario: Usuario, reserva: Reserva) -> None:
        if es_admin(usuario):
            return
        rol = (usuario.rol.nombre if usuario.rol else "").upper()
        if rol == "CLIENTE":
            if usuario.id != reserva.cliente_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado: reserva de otro cliente")
            return
        if rol in ("ENCARGADO", "CAJERO"):
            exigir_sucursal(usuario, reserva.sucursal_destino_id)
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado para consultar reservas")

    async def obtener(self, usuario: Usuario, reserva_id: uuid.UUID) -> ReservaDTO:
        reserva = await self.reserva_repo.buscarPorId(reserva_id)
        if reserva is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
        self._autorizar_lectura(usuario, reserva)
        return await self._a_dto(reserva.id)

    async def obtenerPorCodigo(self, usuario: Usuario, codigo: str) -> ReservaDTO:
        reserva = await self.reserva_repo.buscarPorCodigo(codigo)
        if reserva is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
        self._autorizar_lectura(usuario, reserva)
        return await self._a_dto(reserva.id)

    async def listar(
        self,
        usuario: Usuario,
        cliente_id=None,
        sucursal_id=None,
        estado: Optional[str] = None,
        codigo: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        rol = (usuario.rol.nombre if usuario.rol else "").upper()
        if rol == "CLIENTE":
            if cliente_id is not None and cliente_id != usuario.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo puedes listar tus reservas")
            cliente_id = usuario.id
            if sucursal_id is not None:
                pass  # el cliente puede filtrar sus reservas por sucursal destino
        elif rol in ("ENCARGADO", "CAJERO"):
            if sucursal_id is not None:
                exigir_sucursal(usuario, sucursal_id)
            else:
                propia = usuario.empleado.sucursal_id if usuario.empleado else None
                if propia is None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Indique sucursal_id o asigne sucursal al empleado",
                    )
                sucursal_id = propia
        elif not es_admin(usuario):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado")
        items, total = await self.reserva_repo.listar(
            cliente_id=cliente_id, sucursal_id=sucursal_id, estado=estado,
            codigo=codigo, limit=limit, offset=offset,
        )
        return {
            "total": total, "limit": limit, "offset": offset,
            "items": [await self._a_dto(r.id) for r in items],
        }

    # ---------------- cancelación / expiración ----------------
    def _puede_cancelar(self, usuario: Usuario, reserva: Reserva) -> None:
        if reserva.estado not in ESTADOS_CANCELABLES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No se puede cancelar una reserva en estado {reserva.estado}",
            )
        rol = (usuario.rol.nombre if usuario.rol else "").upper()
        if rol == "CLIENTE":
            if usuario.id != reserva.cliente_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el propietario puede cancelar su reserva")
            return
        if rol in ("ENCARGADO", "ADMINISTRADOR"):
            if not es_admin(usuario):
                exigir_sucursal(usuario, reserva.sucursal_destino_id)
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado para cancelar reservas")

    async def cancelar(self, usuario: Usuario, reserva_id: uuid.UUID) -> ReservaDTO:
        try:
            actual = await self.reserva_repo.buscarPorId(reserva_id)
            if actual is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
            if actual.estado in ("CANCELADA", "VENCIDA", "COMPLETADA"):
                return await self._a_dto(actual.id)  # repeticion idempotente
            self._puede_cancelar(usuario, actual)  # 403/409 tras revalidar estado
            await self._liberar_reserva(actual, "CANCELADA", None)
            salida = await self._a_dto(actual.id)
            await self.db.commit()
            return salida
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise

    async def _liberar_reserva(self, reserva: Reserva, estado_final: str, responsable_id) -> None:
        """Libera el inventario segun su ubicacion y cierra la reserva.

        - Linea RESERVADA en destino: reservado -> disponible + LIBERACION_RESERVA.
        - Traslado SOLICITADO: se cancela (sin movimiento de stock).
        - Traslado APROBADO no despachado: libera comprometido en origen + CANCELADO.
        - Traslado DESPACHADO: continua; al recibirse quedara disponible (no reservado).
        - Traslado RECIBIDO: reservado en destino -> disponible + LIBERACION_RESERVA.
        """
        traslados = await self.reserva_repo.trasladosDeReserva(reserva.id)
        por_detalle: Dict[uuid.UUID, list] = {}
        for t in traslados:
            for d in await self.traslado_repo.detallesDeTraslado(t.id):
                por_detalle.setdefault(d.detalle_reserva_id, []).append((t, d))

        # Bloquea destino + origenes afectados en orden determinista.
        claves = {(reserva.sucursal_destino_id, det.variante_id) for det in reserva.detalles}
        for t, d in [par for pares in por_detalle.values() for par in pares]:
            if t.estado in ("APROBADO", "DESPACHADO"):
                claves.add((t.sucursal_origen_id, d.variante_id))
        filas = await self.inventario_repo.bloquearFilas(list(claves))

        for det in reserva.detalles:
            if det.estado_linea == "RESERVADA" and det.cantidad_reservada > 0:
                fila = filas.get((reserva.sucursal_destino_id, det.variante_id))
                if fila is None or fila.reservado < det.cantidad_reservada:  # pragma: no cover
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Inconsistencia de stock reservado")
                fila.reservado -= det.cantidad_reservada
                fila.disponible += det.cantidad_reservada
                await self.db.flush()
                await self.movimiento_repo.registrar(
                    MovimientoInventario(
                        variante_id=det.variante_id,
                        sucursal_destino_id=reserva.sucursal_destino_id,
                        tipo="LIBERACION_RESERVA",
                        cantidad=det.cantidad_reservada,
                        costo_unitario=Decimal("0"),
                        referencia_tipo="RESERVA",
                        referencia_id=reserva.id,
                        linea_referencia_id=det.id,
                        observacion=f"Liberacion por {estado_final.lower()} de {reserva.codigo}",
                    )
                )
                det.cantidad_liberada += det.cantidad_reservada
                det.cantidad_reservada = 0
                det.estado_linea = "LIBERADA"
            elif det.estado_linea == "PENDIENTE_TRASLADO":
                det.estado_linea = "RECHAZADA"
            await self.db.flush()

        for t, d in [par for pares in por_detalle.values() for par in pares]:
            if t.estado == "SOLICITADO":
                t.estado = "CANCELADO"
                t.motivo_rechazo = f"Reserva {estado_final.lower()}ada"
            elif t.estado == "APROBADO":
                fila = filas.get((t.sucursal_origen_id, d.variante_id))
                if fila is None or fila.comprometido_traslado < d.cantidad:  # pragma: no cover
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Inconsistencia de stock comprometido")
                fila.comprometido_traslado -= d.cantidad
                fila.disponible += d.cantidad
                await self.db.flush()
                await self.movimiento_repo.registrar(
                    MovimientoInventario(
                        variante_id=d.variante_id,
                        sucursal_origen_id=t.sucursal_origen_id,
                        sucursal_destino_id=t.sucursal_destino_id,
                        tipo="LIBERACION_RESERVA",
                        cantidad=d.cantidad,
                        costo_unitario=Decimal("0"),
                        referencia_tipo="TRASLADO",
                        referencia_id=t.id,
                        linea_referencia_id=d.id,
                        observacion=f"Liberacion de compromiso por {estado_final.lower()} de {reserva.codigo}",
                    )
                )
                t.estado = "CANCELADO"
                t.motivo_rechazo = f"Reserva {estado_final.lower()}ada"
            # DESPACHADO continua hasta destino (queda disponible al recibirse).
            await self.db.flush()
        await self.reserva_repo.actualizarEstado(reserva, estado_final)

    # ---------------- preparación y atención CU10 (Entrega 4) ----------------
    def _autorizar_sucursal_staff(self, usuario: Usuario, reserva: Reserva) -> None:
        rol = (usuario.rol.nombre if usuario.rol else "").upper()
        if rol == "ENCARGADO":
            exigir_sucursal(usuario, reserva.sucursal_destino_id)
            return
        if es_admin(usuario):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Encargado de la sucursal o Administrador")

    async def preparar(self, usuario: Usuario, reserva_id: uuid.UUID) -> ReservaDTO:
        """PENDIENTE -> PREPARADA. Sin traslados pendientes ni vencimiento."""
        try:
            reserva = await self.reserva_repo.buscarPorId(reserva_id)
            if reserva is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
            self._autorizar_sucursal_staff(usuario, reserva)
            if reserva.estado == "PREPARADA":
                return await self._a_dto(reserva.id)  # repeticion idempotente
            if reserva.estado != "PENDIENTE":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Solo reservas PENDIENTE pueden prepararse (estado {reserva.estado})",
                )
            if reserva.vence_en is not None and reserva.vence_en <= self.reloj.ahora():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reserva vencida")
            if any(d.estado_linea == "PENDIENTE_TRASLADO" for d in reserva.detalles):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No se puede preparar con traslados pendientes",
                )
            reserva.estado = "PREPARADA"
            reserva.preparada_en = self.reloj.ahora()
            reserva.preparada_por = usuario.id
            await self.db.flush()
            salida = await self._a_dto(reserva.id)
            await self.db.commit()
            return salida
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise

    async def atender(self, usuario: Usuario, reserva_id: uuid.UUID) -> ReservaDTO:
        """PREPARADA -> ATENDIDA (cliente en vestidor)."""
        try:
            reserva = await self.reserva_repo.buscarPorId(reserva_id)
            if reserva is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
            self._autorizar_sucursal_staff(usuario, reserva)
            if reserva.estado == "ATENDIDA":
                return await self._a_dto(reserva.id)  # repeticion idempotente
            if reserva.estado != "PREPARADA":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Solo reservas PREPARADA pueden atenderse (estado {reserva.estado})",
                )
            if reserva.vence_en is not None and reserva.vence_en <= self.reloj.ahora():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Reserva vencida")
            reserva.estado = "ATENDIDA"
            reserva.atendida_en = self.reloj.ahora()
            reserva.atendida_por = usuario.id
            await self.db.flush()
            salida = await self._a_dto(reserva.id)
            await self.db.commit()
            return salida
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise

    async def panelSucursal(
        self,
        usuario: Usuario,
        sucursal_id,
        estado: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        """Cola paginada de la sucursal para polling (sin websocket/push)."""
        rol = (usuario.rol.nombre if usuario.rol else "").upper()
        if rol == "ENCARGADO":
            exigir_sucursal(usuario, sucursal_id)
        elif not es_admin(usuario):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Encargado o Administrador")
        items, total = await self.reserva_repo.listar(
            sucursal_id=sucursal_id, estado=estado, limit=limit, offset=offset
        )
        return {
            "total": total, "limit": limit, "offset": offset,
            "items": [await self._a_dto(r.id) for r in items],
        }

    # ---------------- expiración CU24 ----------------
    async def expirarVencidas(self, ahora: Optional[datetime] = None, limite: int = 100) -> ExpiracionResultadoDTO:
        """Job de vencimiento: idempotente, con advisory lock y SKIP LOCKED.

        Retorna procesadas/expiradas/omitidas/errores. Si otra instancia tiene
        el lock, retorna bloqueo_activo=True sin procesar nada.
        """
        momento = asegurar_utc(ahora) if ahora is not None else self.reloj.ahora()
        resultado = ExpiracionResultadoDTO(procesadas=0)
        try:
            tomada = await self.db.execute(
                text("SELECT pg_try_advisory_lock(hashtext(:nombre))").bindparams(
                    nombre=ADVISORY_LOCK_EXPRIACION
                )
            )
            if not tomada.scalar():
                resultado.bloqueo_activo = True
                await self.db.rollback()
                return resultado
            try:
                candidatas = await self.reserva_repo.buscarVencidas(momento, limite)
                for reserva in candidatas:
                    if reserva.estado not in ESTADOS_NO_TERMINALES_RESERVA:
                        resultado.omitidas.append(str(reserva.id))
                        continue
                    try:
                        async with self.db.begin_nested():
                            actual = await self.reserva_repo.buscarPorId(reserva.id)
                            if actual.estado not in ESTADOS_NO_TERMINALES_RESERVA:
                                resultado.omitidas.append(str(reserva.id))
                                continue
                            await self._liberar_reserva(actual, "VENCIDA", None)
                            resultado.expiradas.append(str(reserva.id))
                    except HTTPException as e:
                        resultado.errores.append(f"{reserva.id}: {e.detail}")
                    except Exception as e:  # pragma: no cover (defensivo)
                        resultado.errores.append(f"{reserva.id}: {type(e).__name__}")
                resultado.procesadas = len(resultado.expiradas) + len(resultado.omitidas) + len(resultado.errores)
            finally:
                await self.db.execute(
                    text("SELECT pg_advisory_unlock(hashtext(:nombre))").bindparams(
                        nombre=ADVISORY_LOCK_EXPRIACION
                    )
                )
            await self.db.commit()
            return resultado
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise
