"""Servicio de sincronización offline (CU04 / C34).

Maneja:
- Emisión de referencia horaria para creación offline (ventana de 8 horas).
- Procesamiento atómico e idempotente de operaciones SOLICITAR_RESERVA.
- Persistencia durable de aceptaciones, rechazos comerciales y conflictos temporales.
- Consulta de operaciones por UUID estable.
"""
import hashlib
import json
import secrets
import string
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from functools import partial
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import settings
from backend.app.core.idempotencia import validar_clave_idempotencia
from backend.app.core.permisos import es_admin
from backend.app.core.reloj import RelojSistema, asegurar_utc, entrada_local_a_utc, a_hora_bolivia
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.inventario.models import MovimientoInventario
from backend.app.core.modules.inventario.repositories.inventario_repository import InventarioRepository
from backend.app.core.modules.inventario.repositories.movimiento_repository import MovimientoRepository
from backend.app.core.modules.catalogo.repositories.variante_repository import VarianteRepository
from backend.app.core.modules.organizacion.repositories.sucursal_repository import SucursalRepository
from backend.app.core.modules.reservas_traslados.models import (
    DetalleReserva,
    OperacionSincronizacion,
    ReferenciaHoraria,
    Reserva,
)
from backend.app.core.modules.reservas_traslados.repositories.reserva_repository import ReservaRepository
from backend.app.core.modules.reservas_traslados.repositories.sincronizacion_repository import SincronizacionRepository
from backend.app.core.modules.reservas_traslados.services.reserva_transaccional import (
    ReservaTransaccional,
    validar_lineas_reserva,
    validar_visita_reserva,
)
from backend.app.core.modules.identidad_empresas.services.plan_service import PlanService
from backend.app.core.modules.reservas_traslados.schemas_sincronizacion import (
    OperacionDTO,
    ReferenciaHorariaDTO,
    ReferenciaHorariaCrearDTO,
    ReferenciaHorariaDetalleDTO,
    ResultadoOperacionDTO,
)
from backend.app.core.modules.ventas_pagos.services.pedido_service import (
    DetallePedido,
    OfertaCompra,
    PedidoCompra,
    ObligacionReembolso,
)
from backend.app.core.modules.ventas_pagos.services.stripe_service import StripeService
from backend.app.core.modules.ventas_pagos.models_ordenes import MetodoPreparado, OrdenPagoCrearDTO

CODIGO_ALFABETO = string.ascii_uppercase + string.digits


def calcular_hash_operacion(dto: OperacionDTO) -> str:
    """Calcula el hash SHA-256 canónico de los campos inmutables de la operación."""
    datos = dto.datos
    if hasattr(datos, "model_dump"):
        raw_datos = datos.model_dump(mode="json")
    elif isinstance(datos, dict):
        raw_datos = dict(datos)
    else:
        raw_datos = getattr(datos, "__dict__", {})

    raw_lineas = raw_datos.get("lineas") or []
    lineas_ordenadas = sorted(
        [
            {
                "cantidad": l.get("cantidad") if isinstance(l, dict) else l.cantidad,
                "variante_id": str(l.get("variante_id") if isinstance(l, dict) else l.variante_id),
            }
            for l in raw_lineas
        ],
        key=lambda x: x["variante_id"],
    )

    if dto.tipo == "SOLICITAR_COMPRA":
        datos_dict = {
            "lineas": lineas_ordenadas,
            "sucursal_id": str(raw_datos.get("sucursal_id")),
            "modalidad": str(raw_datos.get("modalidad", "RECOJO")),
        }
        if raw_datos.get("direccion"):
            datos_dict["direccion"] = str(raw_datos.get("direccion"))
        if raw_datos.get("autorizacion_cobro"):
            ac = raw_datos.get("autorizacion_cobro")
            if hasattr(ac, "model_dump"):
                ac = ac.model_dump(mode="json")
            prep_id = ac.get("preparacion_pago_id") or ac.get("metodo_preparado_id")
            cons = ac.get("consentimiento_id") or ac.get("consentimiento")
            tot = ac.get("total_bob") if ac.get("total_bob") is not None else ac.get("importe_bob")
            datos_dict["autorizacion_cobro"] = {
                "consentimiento": str(cons) if cons is not None else None,
                "metodo_preparado_id": str(prep_id) if prep_id else None,
                "importe_bob": str(tot) if tot is not None else None,
            }
    else:
        visita = raw_datos.get("visita_en")
        if isinstance(visita, datetime):
            visita_str = visita.isoformat()
        else:
            visita_str = str(visita) if visita else None

        datos_dict = {
            "lineas": lineas_ordenadas,
            "sucursal_id": str(raw_datos.get("sucursal_id")),
            "visita_en": visita_str,
        }

    payload = {
        "creada_local_en": dto.creada_local_en.isoformat(),
        "datos": datos_dict,
        "dispositivo_id": str(dto.dispositivo_id),
        "empresa_id": str(dto.empresa_id),
        "operacion_id": str(dto.operacion_id),
        "referencia_horaria_id": str(dto.referencia_horaria_id) if dto.referencia_horaria_id else None,
        "secuencia_local": dto.secuencia_local,
        "tipo": dto.tipo,
        "usuario_id": str(dto.usuario_id),
        "version_esquema": dto.version_esquema,
    }
    texto = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()



class SincronizacionService:
    def __init__(self, db: AsyncSession, reloj=None):
        self.db = db
        self.reloj = reloj or RelojSistema()
        self.sinc_repo = SincronizacionRepository(db)
        self.reserva_repo = ReservaRepository(db)
        self.inventario_repo = InventarioRepository(db)
        self.movimiento_repo = MovimientoRepository(db)
        self.sucursal_repo = SucursalRepository(db)
        self.variante_repo = VarianteRepository(db)
        self.transaccional = ReservaTransaccional(db, self.reloj)

    def _generar_codigo(self) -> str:
        return "FS-" + "".join(secrets.choice(CODIGO_ALFABETO) for _ in range(6))

    async def _codigo_unico(self, empresa_id: Optional[uuid.UUID] = None) -> str:
        for _ in range(5):
            codigo = self._generar_codigo()
            if not await self.reserva_repo.existeCodigo(codigo, empresa_id=empresa_id):
                return codigo
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="No se pudo generar un codigo de reserva unico",
        )

    async def emitirReferenciaHoraria(
        self, usuario: Usuario, dispositivo_id: Optional[uuid.UUID] = None
    ) -> ReferenciaHorariaDTO:
        if not usuario.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario sin empresa asignada",
            )
        dispositivo = dispositivo_id or uuid.uuid4()
        ahora = self.reloj.ahora()
        vence = ahora + timedelta(hours=8)
        ref = ReferenciaHoraria(
            id=uuid.uuid4(),
            empresa_id=usuario.empresa_id,
            usuario_id=usuario.id,
            dispositivo_id=dispositivo,
            emitida_en=ahora,
            vence_en=vence,
        )
        await self.sinc_repo.crearReferencia(ref)
        await self.db.commit()
        return ReferenciaHorariaDTO(
            referencia_horaria_id=ref.id,
            emitida_en=ref.emitida_en,
            vence_en=ref.vence_en,
        )


    async def crearReferenciaHoraria(
        self, usuario: Usuario, dto: ReferenciaHorariaCrearDTO, clave: uuid.UUID
    ) -> ReferenciaHorariaDetalleDTO:
        if not usuario.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario sin empresa asignada",
            )
        if dto.hora_local_en.tzinfo is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="hora_local_en requiere zona horaria con offset explícito",
            )

        if dto.hora_local_en.tzinfo is None or dto.hora_local_en.utcoffset() is None or dto.hora_local_en.utcoffset().total_seconds() != -14400:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="hora_local_en requiere zona horaria con offset explícito de Bolivia (-04:00)",
            )

        ahora_utc = self.reloj.ahora()
        hora_local_utc = dto.hora_local_en.astimezone(self.reloj.ahora().tzinfo)
        desfase_segundos = int((ahora_utc - hora_local_utc).total_seconds())
        tolerancia_segundos = getattr(settings, "SINCRONIZACION_TOLERANCIA_SEGUNDOS", 300)
        politica_version = getattr(settings, "SINCRONIZACION_POLITICA_VERSION", 1)
        duracion_horas = getattr(settings, "SINCRONIZACION_DURACION_HORAS", 8)

        payload_hash = hashlib.sha256(
            json.dumps({
                "dispositivo_id": str(dto.dispositivo_id),
                "hora_local_en": dto.hora_local_en.isoformat(),
            }, sort_keys=True).encode("utf-8")
        ).hexdigest()

        existente = await self.sinc_repo.buscarReferenciaPorIdempotencia(
            clave, usuario.empresa_id
        )
        if existente is not None:
            if existente.hash_solicitud == payload_hash:
                return ReferenciaHorariaDetalleDTO(
                    referencia_horaria_id=existente.id,
                    empresa_id=existente.empresa_id,
                    usuario_id=existente.usuario_id,
                    dispositivo_id=existente.dispositivo_id,
                    hora_central_en=a_hora_bolivia(existente.emitida_en),
                    valida_hasta=a_hora_bolivia(existente.vence_en),
                    tolerancia_segundos=existente.tolerancia_segundos,
                    politica_version=existente.politica_version,
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"codigo": "IDEMPOTENCIA_CONFLICTO", "detalle": "Idempotency-Key ya usada con otra solicitud"},
            )

        if abs(desfase_segundos) > tolerancia_segundos:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "codigo": "TIEMPO_INCOHERENTE",
                    "detalle": f"Desfase de reloj ({desfase_segundos} s) excede la tolerancia permitida ({tolerancia_segundos} s)",
                },
            )

        valida_hasta = ahora_utc + timedelta(hours=duracion_horas)
        ref = ReferenciaHoraria(
            id=uuid.uuid4(),
            empresa_id=usuario.empresa_id,
            usuario_id=usuario.id,
            dispositivo_id=dto.dispositivo_id,
            emitida_en=ahora_utc,
            vence_en=valida_hasta,
            hora_local_en=dto.hora_local_en,
            tolerancia_segundos=tolerancia_segundos,
            politica_version=politica_version,
            desfase_segundos=desfase_segundos,
            clave_idempotencia=clave,
            hash_solicitud=payload_hash,
        )
        try:
            await self.sinc_repo.crearReferencia(ref)
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            existente = await self.sinc_repo.buscarReferenciaPorIdempotencia(
                clave, usuario.empresa_id
            )
            if existente is not None and existente.hash_solicitud == payload_hash:
                return ReferenciaHorariaDetalleDTO(
                    referencia_horaria_id=existente.id,
                    empresa_id=existente.empresa_id,
                    usuario_id=existente.usuario_id,
                    dispositivo_id=existente.dispositivo_id,
                    hora_central_en=a_hora_bolivia(existente.emitida_en),
                    valida_hasta=a_hora_bolivia(existente.vence_en),
                    tolerancia_segundos=existente.tolerancia_segundos,
                    politica_version=existente.politica_version,
                )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"codigo": "TIEMPO_INCOHERENTE", "detalle": "Conflicto concurrente al registrar referencia horaria"},
            )

        return ReferenciaHorariaDetalleDTO(
            referencia_horaria_id=ref.id,
            empresa_id=ref.empresa_id,
            usuario_id=ref.usuario_id,
            dispositivo_id=ref.dispositivo_id,
            hora_central_en=a_hora_bolivia(ref.emitida_en),
            valida_hasta=a_hora_bolivia(ref.vence_en),
            tolerancia_segundos=ref.tolerancia_segundos,
            politica_version=ref.politica_version,
        )

    async def procesarOperacion(
        self, usuario: Usuario, dto: OperacionDTO
    ) -> ResultadoOperacionDTO:
        if dto.tipo not in ("SOLICITAR_RESERVA", "SOLICITAR_COMPRA"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tipo de operacion {dto.tipo} no soportado en esta entrega",
            )
        if not usuario.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario sin empresa asignada",
            )
        if dto.empresa_id != usuario.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Empresa de la operacion no coincide con la sesion del usuario",
            )
        if dto.usuario_id != usuario.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuario de la operacion no coincide con la sesion actual",
            )

        digest = calcular_hash_operacion(dto)

        if dto.tipo == "SOLICITAR_COMPRA":
            return await self._procesar_solicitar_compra(usuario, dto, digest)

        if isinstance(dto.datos, dict):
            if dto.tipo == "SOLICITAR_RESERVA":
                dto.datos = OperacionDatosReservaDTO.model_validate(dto.datos)
            elif dto.tipo == "SOLICITAR_COMPRA":
                dto.datos = OperacionDatosCompraDTO.model_validate(dto.datos)

        # Las lineas duplicadas son un error de forma (400), no un rechazo
        # comercial: nunca deben llegar a apartar stock ni violar el UNIQUE.
        validar_lineas_reserva(dto.datos.lineas)


        # Reintento / conflicto dentro del ambito autorizado (empresa + actor).
        existente = await self.sinc_repo.buscarOperacionPorActor(
            dto.operacion_id, usuario.id, usuario.empresa_id
        )
        if existente is not None:
            return self._resultado_de_operacion(existente, digest)

        ahora = self.reloj.ahora()

        # 0. Capacidad y suscripción del plan de la empresa (CU02 / C12 / C28)
        plan_service = PlanService(self.db)
        capacidad = await plan_service.validar_capacidad(
            usuario.empresa_id, ahora, es_offline=True
        )
        if not capacidad.habilitado:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="RECHAZADA",
                    codigo="PLAN_NO_HABILITADO",
                    detalle=capacidad.motivo_rechazo or "El plan de la empresa no está habilitado",
                ),
            )
        creada_local = asegurar_utc(dto.creada_local_en)
        origen_plazo = creada_local
        vence_en = origen_plazo + timedelta(hours=24)

        # Referencia horaria: si no viene en el body, buscar referencia previa verificable
        if dto.referencia_horaria_id is None:
            ref = await self.sinc_repo.buscarUltimaReferenciaVerificable(
                dto.empresa_id, dto.usuario_id, dto.dispositivo_id
            )
            if ref is None:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="CONFLICTO",
                        codigo="TIEMPO_INCOHERENTE",
                        detalle="Operacion offline no incluye referencia_horaria_id y no se encontro referencia previa verificable",
                    ),
                )
        else:
            ref = await self.sinc_repo.buscarReferencia(
                dto.referencia_horaria_id,
                empresa_id=dto.empresa_id,
                usuario_id=dto.usuario_id,
                dispositivo_id=dto.dispositivo_id,
            )
            if ref is None:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="CONFLICTO",
                        codigo="TIEMPO_INCOHERENTE",
                        detalle="Referencia horaria inexistente o no valida para el actor y dispositivo",
                    ),
                )

        ref_emitida = asegurar_utc(ref.emitida_en)
        ref_vence = asegurar_utc(ref.vence_en)
        desfase_s = ref.desfase_segundos if ref.desfase_segundos is not None else 0
        desfase = timedelta(seconds=desfase_s)
        creacion_estimada_central = creada_local + desfase
        tolerancia_s = ref.tolerancia_segundos if ref.tolerancia_segundos is not None else 300
        tolerancia = timedelta(seconds=tolerancia_s)

        # Ventana de emisión:
        if ref.hora_local_en is not None:
            if creacion_estimada_central < ref_emitida or creacion_estimada_central >= ref_vence:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="CONFLICTO",
                        codigo="TIEMPO_INCOHERENTE",
                        detalle="Fecha de creacion estimada fuera de la ventana de vigencia de la referencia horaria",
                    ),
                )
        else:
            if creacion_estimada_central < ref_emitida - tolerancia or creacion_estimada_central > ref_vence + tolerancia:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="CONFLICTO",
                        codigo="TIEMPO_INCOHERENTE",
                        detalle="Fecha de creacion local fuera de la ventana de 8 horas de la referencia",
                    ),
                )

        # creacion_estimada_central <= recibida_en + tolerancia
        if creacion_estimada_central > ahora + tolerancia:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="CONFLICTO",
                    codigo="TIEMPO_INCOHERENTE",
                    detalle="Fecha de creacion estimada en el futuro respecto a la recepcion central",
                ),
            )

        # recibida_en < creada_local_utc + 24 h
        if ahora >= origen_plazo + timedelta(hours=24):
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="RECHAZADA",
                    codigo="SOLICITUD_VENCIDA",
                    detalle="Han transcurrido mas de 24 horas desde la creacion local original",
                ),
            )

        # Visita obligatoria: posterior a la recepción y dentro de las 24 h contadas desde origen_plazo
        visita = asegurar_utc(dto.datos.visita_en)
        if visita <= ahora:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="CONFLICTO",
                    codigo="TIEMPO_INCOHERENTE",
                    detalle="La fecha de visita ya transcurrio antes de la recepcion de la sincronizacion en el servidor",
                ),
            )
        if visita > vence_en:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="CONFLICTO",
                    codigo="TIEMPO_INCOHERENTE",
                    detalle="La fecha de visita debe estar dentro de la vigencia de 24 horas contadas desde la creacion local original",
                ),
            )
        if visita < origen_plazo:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="CONFLICTO",
                    codigo="TIEMPO_INCOHERENTE",
                    detalle="La fecha de visita no puede ser anterior a la creacion de la solicitud",
                ),
            )

        # 5. Sucursal y variantes dentro de la empresa; un fallo de ambito se
        # traduce en rechazo durable sin apartar stock.
        try:
            await self.transaccional.validar_sucursal_destino(
                dto.datos.sucursal_id, dto.empresa_id
            )
            variantes = await self.transaccional.validar_variantes(
                dto.datos.lineas, dto.empresa_id
            )
        except HTTPException as e:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="RECHAZADA",
                    codigo="SIN_STOCK",
                    detalle=str(e.detail),
                ),
            )

        # 6. Bloqueo determinista y decision atomica sin traslados.
        filas = await self.transaccional.bloquear_filas(
            dto.datos.sucursal_id, dto.datos.lineas, incluir_origenes=False
        )
        planes, faltante = self.transaccional.planificar_apartado(
            filas,
            dto.datos.sucursal_id,
            dto.datos.lineas,
            permitir_traslado=False,
            variantes=variantes,
        )
        if faltante is not None:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="RECHAZADA",
                    codigo="SIN_STOCK",
                    detalle=faltante,
                ),
            )

        # 7. Aceptación atómica en una única transacción
        return await self._persistir_con_reintento(
            dto,
            digest,
            partial(
                self._aceptar_operacion_en_tx,
                dto=dto,
                digest=digest,
                ahora=ahora,
                creada_local=creada_local,
                filas=filas,
                planes=planes,
                variantes=variantes,
            ),
        )

    def _resultado_de_operacion(
        self, existente: OperacionSincronizacion, digest: str
    ) -> ResultadoOperacionDTO:
        """Devuelve el resultado durable o 409 si el UUID se reutilizó con otro cuerpo."""
        if existente.hash_solicitud == digest:
            return ResultadoOperacionDTO.model_validate(existente.resultado)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "codigo": "OPERACION_MODIFICADA",
                "detalle": "operacion_id reutilizado con contenido distinto",
            },
        )

    async def _persistir_con_reintento(self, dto: OperacionDTO, digest: str, operacion):
        """Serializa reintentos concurrentes del mismo `operacion_id`.

        Dos POST simultáneos con idéntico actor/empresa/cuerpo compiten por
        `uq_operaciones_actor_uuid`. El perdedor revierte su transacción
        (incluido cualquier apartado de stock) y devuelve el resultado durable
        del ganador; si el cuerpo difiere responde 409 OPERACION_MODIFICADA.
        """
        try:
            return await operacion()
        except IntegrityError as e:
            await self.db.rollback()
            mensaje = str(getattr(e, "orig", e))
            if "uq_operaciones_actor_uuid" in mensaje or "operacion_id" in mensaje:
                existente = await self.sinc_repo.buscarOperacionPorActor(
                    dto.operacion_id, dto.usuario_id, dto.empresa_id
                )
                if existente is not None:
                    return self._resultado_de_operacion(existente, digest)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "codigo": "OPERACION_MODIFICADA",
                        "detalle": "Conflicto concurrente al registrar la operacion",
                    },
                )
            raise

    async def _persistir_rechazo_o_conflicto(
        self,
        dto: OperacionDTO,
        digest: str,
        ahora: datetime,
        estado: str,
        codigo: str,
        detalle: str,
    ) -> ResultadoOperacionDTO:
        ref_id_bd = dto.referencia_horaria_id
        if ref_id_bd is not None:
            ref = await self.sinc_repo.buscarReferencia(
                ref_id_bd,
                empresa_id=dto.empresa_id,
                usuario_id=dto.usuario_id,
                dispositivo_id=dto.dispositivo_id,
            )
            if ref is None:
                ref_id_bd = None

        resultado_dict = {
            "operacion_id": str(dto.operacion_id),
            "estado": estado,
            "codigo": codigo,
            "recibida_en": a_hora_bolivia(ahora).isoformat(),
            "detalle": detalle,
        }
        op = OperacionSincronizacion(
            id=uuid.uuid4(),
            empresa_id=dto.empresa_id,
            usuario_id=dto.usuario_id,
            operacion_id=dto.operacion_id,
            tipo=dto.tipo,
            version_esquema=dto.version_esquema,
            dispositivo_id=dto.dispositivo_id,
            secuencia_local=dto.secuencia_local,
            creada_local_en=asegurar_utc(dto.creada_local_en),
            recibida_en=ahora,
            aceptada_en=None,
            referencia_horaria_id=ref_id_bd,
            hash_solicitud=digest,
            solicitud=dto.model_dump(mode="json"),
            estado=estado,
            codigo=codigo,
            detalle=detalle,
            resultado=resultado_dict,
            recurso_id=None,
            revision=1,
        )
        self.db.add(op)
        await self.db.commit()
        return ResultadoOperacionDTO(**resultado_dict)

    async def _aceptar_operacion_en_tx(
        self,
        dto: OperacionDTO,
        digest: str,
        ahora: datetime,
        creada_local: datetime,
        filas: dict,
        planes: list,
        variantes: dict,
    ) -> ResultadoOperacionDTO:
        try:
            reserva_id = uuid.uuid4()
            vence_en = creada_local + timedelta(hours=24)
            codigo_reserva = await self._codigo_unico(dto.empresa_id)

            resultado_dict = {
                "operacion_id": str(dto.operacion_id),
                "estado": "ACEPTADA",
                "codigo": "OK",
                "recibida_en": a_hora_bolivia(ahora).isoformat(),
                "aceptada_en": a_hora_bolivia(ahora).isoformat(),
                "recurso_id": str(reserva_id),
                "vence_en": a_hora_bolivia(vence_en).isoformat(),
                "detalle": "Reserva aceptada",
            }

            # 1. Operación de sincronización
            op = OperacionSincronizacion(
                id=uuid.uuid4(),
                empresa_id=dto.empresa_id,
                usuario_id=dto.usuario_id,
                operacion_id=dto.operacion_id,
                tipo=dto.tipo,
                version_esquema=dto.version_esquema,
                dispositivo_id=dto.dispositivo_id,
                secuencia_local=dto.secuencia_local,
                creada_local_en=creada_local,
                recibida_en=ahora,
                aceptada_en=ahora,
                referencia_horaria_id=dto.referencia_horaria_id,
                hash_solicitud=digest,
                solicitud=dto.model_dump(mode="json"),
                estado="ACEPTADA",
                codigo="OK",
                detalle="Reserva aceptada",
                recurso_id=reserva_id,
                revision=1,
                resultado=resultado_dict,
            )
            self.db.add(op)
            await self.db.flush()

            # 2. Reserva vinculada: origen del plazo es la creación local original; vence a las 24 h
            reserva = Reserva(
                id=reserva_id,
                empresa_id=dto.empresa_id,
                cliente_id=dto.usuario_id,
                sucursal_destino_id=dto.datos.sucursal_id,
                codigo=codigo_reserva,
                estado="PENDIENTE",
                revision=1,
                fecha_creacion=ahora,
                origen_plazo_en=creada_local,
                vence_en=vence_en,
                fecha_visita=entrada_local_a_utc(dto.datos.visita_en),
                observacion=f"Reserva offline {dto.operacion_id}",
                clave_idempotencia=None,
                hash_solicitud=digest,
                operacion_sincronizacion_id=op.id,
            )
            self.db.add(reserva)
            await self.db.flush()

            # 3. Líneas, stock apartado y Kardex con el núcleo compartido.
            await self.transaccional.persistir_apartado(
                reserva=reserva,
                planes=planes,
                variantes=variantes,
                filas=filas,
                permitir_traslado=False,
                cliente_id=dto.usuario_id,
                observacion_kardex=f"Reserva offline {reserva.codigo}",
            )

            await self.db.commit()
            return ResultadoOperacionDTO(**resultado_dict)
        except IntegrityError:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise

    async def _procesar_solicitar_compra(
        self, usuario: Usuario, dto: OperacionDTO, digest: str
    ) -> ResultadoOperacionDTO:
        # Reintento / deduplicación
        existente = await self.sinc_repo.buscarOperacionPorActor(
            dto.operacion_id, usuario.id, usuario.empresa_id
        )
        if existente is not None:
            return self._resultado_de_operacion(existente, digest)

        ahora = self.reloj.ahora()

        # 0. Capacidad y suscripción del plan
        plan_service = PlanService(self.db)
        capacidad = await plan_service.validar_capacidad(
            usuario.empresa_id, ahora, es_offline=True
        )
        if not capacidad.habilitado:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="RECHAZADA",
                    codigo="PLAN_NO_HABILITADO",
                    detalle=capacidad.motivo_rechazo or "El plan de la empresa no está habilitado",
                ),
            )

        creada_local = asegurar_utc(dto.creada_local_en)
        origen_plazo = creada_local
        vence_en = origen_plazo + timedelta(hours=24)

        # Referencia horaria
        if dto.referencia_horaria_id is None:
            ref = await self.sinc_repo.buscarUltimaReferenciaVerificable(
                dto.empresa_id, dto.usuario_id, dto.dispositivo_id
            )
            if ref is None:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="CONFLICTO",
                        codigo="TIEMPO_INCOHERENTE",
                        detalle="Operacion offline no incluye referencia_horaria_id y no se encontro referencia previa verificable",
                    ),
                )
        else:
            ref = await self.sinc_repo.buscarReferencia(
                dto.referencia_horaria_id,
                empresa_id=dto.empresa_id,
                usuario_id=dto.usuario_id,
                dispositivo_id=dto.dispositivo_id,
            )
            if ref is None:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="CONFLICTO",
                        codigo="TIEMPO_INCOHERENTE",
                        detalle="Referencia horaria inexistente o no valida para el actor y dispositivo",
                    ),
                )

        ref_emitida = asegurar_utc(ref.emitida_en)
        ref_vence = asegurar_utc(ref.vence_en)
        desfase_s = ref.desfase_segundos if ref.desfase_segundos is not None else 0
        desfase = timedelta(seconds=desfase_s)
        creacion_estimada_central = creada_local + desfase
        tolerancia_s = ref.tolerancia_segundos if ref.tolerancia_segundos is not None else 300
        tolerancia = timedelta(seconds=tolerancia_s)

        if ref.hora_local_en is not None:
            if creacion_estimada_central < ref_emitida or creacion_estimada_central >= ref_vence:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="CONFLICTO",
                        codigo="TIEMPO_INCOHERENTE",
                        detalle="Fecha de creacion estimada fuera de la ventana de vigencia de la referencia horaria",
                    ),
                )
        else:
            if creacion_estimada_central < ref_emitida - tolerancia or creacion_estimada_central > ref_vence + tolerancia:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="CONFLICTO",
                        codigo="TIEMPO_INCOHERENTE",
                        detalle="Fecha de creacion local fuera de la ventana de 8 horas de la referencia",
                    ),
                )

        if creacion_estimada_central > ahora + tolerancia:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="CONFLICTO",
                    codigo="TIEMPO_INCOHERENTE",
                    detalle="Fecha de creacion estimada en el futuro respecto a la recepcion central",
                ),
            )

        if ahora >= origen_plazo + timedelta(hours=24):
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="RECHAZADA",
                    codigo="SOLICITUD_VENCIDA",
                    detalle="Han transcurrido mas de 24 horas desde la creacion local original",
                ),
            )

        # Parsear datos de compra
        datos = dto.datos
        if hasattr(datos, "model_dump"):
            datos_dict = datos.model_dump(mode="json")
        elif isinstance(datos, dict):
            datos_dict = dict(datos)
        else:
            datos_dict = getattr(datos, "__dict__", {})

        sucursal_id_raw = datos_dict.get("sucursal_id")
        try:
            sucursal_id = uuid.UUID(str(sucursal_id_raw))
        except (ValueError, TypeError):
            sucursal_id = None

        if sucursal_id is None:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="RECHAZADA",
                    codigo="SIN_STOCK",
                    detalle="Sucursal no válida en la solicitud",
                ),
            )

        sucursal = await self.sucursal_repo.buscarPorId(sucursal_id)
        if sucursal is None or sucursal.empresa_id != usuario.empresa_id:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="RECHAZADA",
                    codigo="SIN_STOCK",
                    detalle="Sucursal no encontrada o inactiva en la empresa",
                ),
            )

        raw_lineas = datos_dict.get("lineas") or []
        if not raw_lineas:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="RECHAZADA",
                    codigo="SIN_STOCK",
                    detalle="La compra no contiene líneas",
                ),
            )

        # Validar y calcular importes centrales
        subtotal_central = Decimal("0.00")
        lineas_procesadas = []
        for l in raw_lineas:
            vid = uuid.UUID(str(l.get("variante_id") if isinstance(l, dict) else l.variante_id))
            cant = int(l.get("cantidad") if isinstance(l, dict) else l.cantidad)
            var = await self.variante_repo.buscarPorId(vid)
            if var is None or var.empresa_id != usuario.empresa_id:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="RECHAZADA",
                        codigo="SIN_STOCK",
                        detalle=f"Variante {vid} no existe en la empresa",
                    ),
                )
            p_unit = Decimal(str(var.precio or 0))
            tot_linea = p_unit * cant
            subtotal_central += tot_linea
            lineas_procesadas.append((var, cant, p_unit, tot_linea))

        modalidad = str(datos_dict.get("modalidad", "RECOJO")).upper()
        envio_central = Decimal("15.00") if modalidad == "DELIVERY" else Decimal("0.00")
        total_central = subtotal_central + envio_central

        # Manejo según versión de esquema
        if dto.version_esquema in (1, 2):
            # Versiones 1 y 2: conservan semántica anterior y jamás cobran automáticamente
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._crear_compra_v1_v2_en_tx,
                    dto=dto,
                    digest=digest,
                    ahora=ahora,
                    usuario=usuario,
                    sucursal_id=sucursal_id,
                    modalidad=modalidad,
                    direccion=datos_dict.get("direccion"),
                    subtotal=subtotal_central,
                    envio=envio_central,
                    total=total_central,
                    lineas=lineas_procesadas,
                ),
            )

        # Versión 3: requiere autorización de cobro completa y comprobación contra oferta central
        aut = datos_dict.get("autorizacion_cobro")
        if not aut:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="PENDIENTE_INTERVENCION",
                    codigo="AUTORIZACION_REQUERIDA",
                    detalle="Solicitud guardada; requiere autorización y método preparado para cobro automático",
                ),
            )

        if hasattr(aut, "model_dump"):
            aut = aut.model_dump(mode="json")

        consentimiento = aut.get("consentimiento_id") or aut.get("consentimiento")
        if consentimiento is None or (isinstance(consentimiento, bool) and not consentimiento):
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="PENDIENTE_INTERVENCION",
                    codigo="AUTORIZACION_REQUERIDA",
                    detalle="Solicitud guardada; requiere autorización y método preparado para cobro automático",
                ),
            )

        metodo_preparado_id_raw = aut.get("preparacion_pago_id") or aut.get("metodo_preparado_id")
        if not metodo_preparado_id_raw:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="PENDIENTE_INTERVENCION",
                    codigo="AUTORIZACION_REQUERIDA",
                    detalle="Solicitud guardada; requiere autorización y método preparado para cobro automático",
                ),
            )

        try:
            metodo_preparado_id = uuid.UUID(str(metodo_preparado_id_raw))
        except (ValueError, TypeError):
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="PENDIENTE_INTERVENCION",
                    codigo="AUTORIZACION_REQUERIDA",
                    detalle="UUID de método preparado inválido",
                ),
            )

        if aut.get("permite_cobro_al_reconectar") is False:
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="PENDIENTE_INTERVENCION",
                    codigo="AUTORIZACION_REQUERIDA",
                    detalle="Solicitud no autoriza cobro automático al reconectar",
                ),
            )

        # Consultar tasa vigente central y calcular oferta central
        stmt_tasa = text("SELECT id, tasa_bob_por_usd FROM plataforma.tasas_cambio ORDER BY vigente_desde DESC LIMIT 1")
        r_tasa = await self.db.execute(stmt_tasa)
        f_tasa = r_tasa.first()
        tasa_central_val = Decimal(str(f_tasa[1])) if f_tasa else Decimal("6.96")
        total_usd_central = (total_central / tasa_central_val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        # Validar oferta autorizada contra la oferta central
        importe_bob_cliente = aut.get("total_bob") if aut.get("total_bob") is not None else aut.get("importe_bob")
        if importe_bob_cliente is not None:
            if Decimal(str(importe_bob_cliente)) != total_central:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="REQUIERE_NUEVA_ACEPTACION",
                        codigo="PRECIO_CAMBIADO",
                        detalle=f"El importe central ({total_central} BOB) difiere del autorizado ({importe_bob_cliente} BOB)",
                    ),
                )

        moneda_cobro = aut.get("moneda_cobro")
        if moneda_cobro and moneda_cobro != "USD":
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="REQUIERE_NUEVA_ACEPTACION",
                    codigo="PRECIO_CAMBIADO",
                    detalle="Moneda de cobro inválida (solo se admite USD)",
                ),
            )

        tasa_cliente = aut.get("tasa_bob_por_usd") if aut.get("tasa_bob_por_usd") is not None else aut.get("tasa")
        if tasa_cliente is not None:
            if Decimal(str(tasa_cliente)) != tasa_central_val:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="REQUIERE_NUEVA_ACEPTACION",
                        codigo="PRECIO_CAMBIADO",
                        detalle=f"La tasa autorizada ({tasa_cliente}) difiere de la tasa vigente ({tasa_central_val})",
                    ),
                )

        usd_cliente = aut.get("importe_cobro") if aut.get("importe_cobro") is not None else aut.get("importe_usd")
        if usd_cliente is not None:
            if Decimal(str(usd_cliente)) != total_usd_central:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="REQUIERE_NUEVA_ACEPTACION",
                        codigo="PRECIO_CAMBIADO",
                        detalle=f"El importe USD autorizado ({usd_cliente}) difiere del central ({total_usd_central})",
                    ),
                )

        vig_cliente = aut.get("vigente_hasta") or aut.get("vigencia_hasta")
        if vig_cliente:
            if isinstance(vig_cliente, str):
                vig_dt = datetime.fromisoformat(vig_cliente.replace("Z", "+00:00"))
            else:
                vig_dt = vig_cliente
            if asegurar_utc(vig_dt) <= ahora:
                return await self._persistir_con_reintento(
                    dto,
                    digest,
                    partial(
                        self._persistir_rechazo_o_conflicto,
                        dto,
                        digest,
                        ahora,
                        estado="REQUIERE_NUEVA_ACEPTACION",
                        codigo="PRECIO_CAMBIADO",
                        detalle="La autorización de cobro ha expirado",
                    ),
                )

        # Validar método preparado en base de datos
        stmt_mp = select(MetodoPreparado).where(
            MetodoPreparado.id == metodo_preparado_id,
            MetodoPreparado.empresa_id == usuario.empresa_id,
            MetodoPreparado.cliente_id == usuario.id,
        )
        mp = (await self.db.execute(stmt_mp)).scalars().first()
        if mp is None or mp.estado != "LISTO":
            return await self._persistir_con_reintento(
                dto,
                digest,
                partial(
                    self._persistir_rechazo_o_conflicto,
                    dto,
                    digest,
                    ahora,
                    estado="PENDIENTE_INTERVENCION",
                    codigo="AUTORIZACION_REQUERIDA",
                    detalle="Método preparado no encontrado, no listo o no pertenece al cliente",
                ),
            )

        # Autorización completa y válida: crear pedido pendiente e integrar cobro real con Stripe
        return await self._persistir_con_reintento(
            dto,
            digest,
            partial(
                self._crear_compra_v3_y_cobrar_en_tx,
                dto=dto,
                digest=digest,
                ahora=ahora,
                usuario=usuario,
                sucursal_id=sucursal_id,
                modalidad=modalidad,
                direccion=datos_dict.get("direccion"),
                subtotal=subtotal_central,
                envio=envio_central,
                total=total_central,
                metodo_preparado_id=metodo_preparado_id,
                lineas=lineas_procesadas,
            ),
        )

    async def _crear_compra_v1_v2_en_tx(
        self,
        dto: OperacionDTO,
        digest: str,
        ahora: datetime,
        usuario: Usuario,
        sucursal_id: uuid.UUID,
        modalidad: str,
        direccion: Optional[str],
        subtotal: Decimal,
        envio: Decimal,
        total: Decimal,
        lineas: List[Tuple[Any, int, Decimal, Decimal]],
    ) -> ResultadoOperacionDTO:
        pedido_id = uuid.uuid4()
        pedido = PedidoCompra(
            id=pedido_id,
            empresa_id=usuario.empresa_id,
            cliente_id=usuario.id,
            sucursal_id=sucursal_id,
            operacion_id=dto.operacion_id,
            metodo_preparado_id=None,
            modalidad=modalidad,
            direccion=direccion if modalidad == "DELIVERY" else None,
            subtotal_bob=subtotal,
            descuento_bob=Decimal("0.00"),
            envio_bob=envio,
            total_bob=total,
            estado="BORRADOR",
            estado_pago="SIN_PAGO",
            estado_cumplimiento="SIN_ASIGNACION",
            revision=1,
            creado_en=ahora,
            actualizado_en=ahora,
        )
        self.db.add(pedido)

        doc_lineas = []
        for var, cant, precio, tot in lineas:
            det = DetallePedido(
                id=uuid.uuid4(),
                empresa_id=usuario.empresa_id,
                pedido_id=pedido_id,
                variante_id=var.id,
                cantidad=cant,
                precio_unitario_bob=precio,
                descuento_bob=Decimal("0.00"),
                total_bob=tot,
                oferta_revision=1,
            )
            self.db.add(det)
            doc_lineas.append(
                {
                    "variante_id": str(var.id),
                    "cantidad": cant,
                    "precio_unitario_bob": str(precio),
                    "total_bob": str(tot),
                }
            )

        doc_oferta = {
            "pedido_id": str(pedido_id),
            "revision": 1,
            "lineas": doc_lineas,
            "subtotal_bob": str(subtotal),
            "descuento_bob": "0.00",
            "envio_bob": str(envio),
            "total_bob": str(total),
        }
        oferta = OfertaCompra(
            id=uuid.uuid4(),
            empresa_id=usuario.empresa_id,
            pedido_id=pedido_id,
            revision=1,
            documento=doc_oferta,
            documento_hash=hashlib.sha256(json.dumps(doc_oferta, sort_keys=True).encode("utf-8")).hexdigest(),
            subtotal_bob=subtotal,
            descuento_bob=Decimal("0.00"),
            envio_bob=envio,
            total_bob=total,
            vigente_hasta=ahora + timedelta(hours=24),
            creada_en=ahora,
        )
        self.db.add(oferta)

        resultado = ResultadoOperacionDTO(
            operacion_id=dto.operacion_id,
            estado="PENDIENTE_PAGO",
            codigo="OK",
            recibida_en=ahora,
            aceptada_en=ahora,
            recurso_id=pedido.id,
            vence_en=ahora + timedelta(hours=24),
            detalle="Compra offline registrada en central; pendiente de pago por el cliente",
            revision=1,
        )

        op_rec = OperacionSincronizacion(
            id=uuid.uuid4(),
            empresa_id=dto.empresa_id,
            usuario_id=dto.usuario_id,
            operacion_id=dto.operacion_id,
            tipo=dto.tipo,
            version_esquema=dto.version_esquema,
            dispositivo_id=dto.dispositivo_id,
            secuencia_local=dto.secuencia_local,
            creada_local_en=asegurar_utc(dto.creada_local_en),
            recibida_en=ahora,
            aceptada_en=resultado.aceptada_en,
            referencia_horaria_id=dto.referencia_horaria_id,
            hash_solicitud=digest,
            solicitud=dto.model_dump(mode="json"),
            estado=resultado.estado,
            codigo=resultado.codigo,
            detalle=resultado.detalle,
            resultado=resultado.model_dump(mode="json"),
            recurso_id=pedido.id,
            revision=1,
        )
        self.db.add(op_rec)
        await self.db.commit()
        return resultado

    async def _crear_compra_v3_y_cobrar_en_tx(
        self,
        dto: OperacionDTO,
        digest: str,
        ahora: datetime,
        usuario: Usuario,
        sucursal_id: uuid.UUID,
        modalidad: str,
        direccion: Optional[str],
        subtotal: Decimal,
        envio: Decimal,
        total: Decimal,
        metodo_preparado_id: uuid.UUID,
        lineas: List[Tuple[Any, int, Decimal, Decimal]],
    ) -> ResultadoOperacionDTO:
        # 1. Crear pedido en estado pendiente de verificación, SIN compromiso de stock ni reembolso
        pedido_id = uuid.uuid4()
        pedido = PedidoCompra(
            id=pedido_id,
            empresa_id=usuario.empresa_id,
            cliente_id=usuario.id,
            sucursal_id=sucursal_id,
            operacion_id=dto.operacion_id,
            metodo_preparado_id=metodo_preparado_id,
            modalidad=modalidad,
            direccion=direccion if modalidad == "DELIVERY" else None,
            subtotal_bob=subtotal,
            descuento_bob=Decimal("0.00"),
            envio_bob=envio,
            total_bob=total,
            estado="BORRADOR",
            estado_pago="EN_VERIFICACION",
            estado_cumplimiento="SIN_ASIGNACION",
            revision=1,
            creado_en=ahora,
            actualizado_en=ahora,
        )
        self.db.add(pedido)

        doc_lineas = []
        for var, cant, precio, tot in lineas:
            det = DetallePedido(
                id=uuid.uuid4(),
                empresa_id=usuario.empresa_id,
                pedido_id=pedido_id,
                variante_id=var.id,
                cantidad=cant,
                precio_unitario_bob=precio,
                descuento_bob=Decimal("0.00"),
                total_bob=tot,
                oferta_revision=1,
            )
            self.db.add(det)
            doc_lineas.append(
                {
                    "variante_id": str(var.id),
                    "cantidad": cant,
                    "precio_unitario_bob": str(precio),
                    "total_bob": str(tot),
                }
            )

        doc_oferta = {
            "pedido_id": str(pedido_id),
            "revision": 1,
            "lineas": doc_lineas,
            "subtotal_bob": str(subtotal),
            "descuento_bob": "0.00",
            "envio_bob": str(envio),
            "total_bob": str(total),
        }
        oferta = OfertaCompra(
            id=uuid.uuid4(),
            empresa_id=usuario.empresa_id,
            pedido_id=pedido_id,
            revision=1,
            documento=doc_oferta,
            documento_hash=hashlib.sha256(json.dumps(doc_oferta, sort_keys=True).encode("utf-8")).hexdigest(),
            subtotal_bob=subtotal,
            descuento_bob=Decimal("0.00"),
            envio_bob=envio,
            total_bob=total,
            vigente_hasta=ahora + timedelta(hours=24),
            creada_en=ahora,
        )
        self.db.add(oferta)
        await self.db.flush()

        # 2. Integrar cobro real mediante StripeService
        stripe_svc = StripeService(self.db, reloj=self.reloj)
        orden_dto = await stripe_svc.crear_orden_pago(
            usuario=usuario,
            datos=OrdenPagoCrearDTO(
                contexto="PEDIDO",
                recurso_id=pedido.id,
                metodo_preparado_id=metodo_preparado_id,
                consentimiento_cobro_posterior=True,
            ),
            clave_idempotencia=dto.operacion_id,
            autocommit=False,
        )

        # 3. Determinar resultado según estado devuelto por Stripe / pasarela
        if orden_dto.estado == "REQUIERE_ACCION_CLIENTE":
            resultado = ResultadoOperacionDTO(
                operacion_id=dto.operacion_id,
                estado="REQUIERE_ACCION_CLIENTE",
                codigo="ACCION_CLIENTE_REQUERIDA",
                recibida_en=ahora,
                recurso_id=pedido.id,
                vence_en=ahora + timedelta(hours=24),
                detalle="El proveedor de pago exige verificación 3D Secure del cliente",
                revision=1,
            )
        elif orden_dto.estado == "CAPTURADO":
            await self.db.refresh(pedido)
            if pedido.estado_cumplimiento == "COMPROMETIDO":
                resultado = ResultadoOperacionDTO(
                    operacion_id=dto.operacion_id,
                    estado="ACEPTADA",
                    codigo="OK",
                    recibida_en=ahora,
                    aceptada_en=ahora,
                    recurso_id=pedido.id,
                    vence_en=ahora + timedelta(hours=24),
                    detalle="Compra offline sincronizada y stock asignado exitosamente",
                    revision=1,
                )
            else:
                resultado = ResultadoOperacionDTO(
                    operacion_id=dto.operacion_id,
                    estado="ACEPTADA",
                    codigo="SIN_STOCK",
                    recibida_en=ahora,
                    aceptada_en=ahora,
                    recurso_id=pedido.id,
                    vence_en=ahora + timedelta(hours=24),
                    detalle="Pedido cobrado pero sin stock disponible; derivado a reembolso íntegro CU27",
                    revision=1,
                )
        else:
            resultado = ResultadoOperacionDTO(
                operacion_id=dto.operacion_id,
                estado="PENDIENTE_PAGO",
                codigo="PAGO_EN_VERIFICACION",
                recibida_en=ahora,
                recurso_id=pedido.id,
                vence_en=ahora + timedelta(hours=24),
                detalle="Pago en verificación con el proveedor",
                revision=1,
            )

        op_rec = OperacionSincronizacion(
            id=uuid.uuid4(),
            empresa_id=dto.empresa_id,
            usuario_id=dto.usuario_id,
            operacion_id=dto.operacion_id,
            tipo=dto.tipo,
            version_esquema=dto.version_esquema,
            dispositivo_id=dto.dispositivo_id,
            secuencia_local=dto.secuencia_local,
            creada_local_en=asegurar_utc(dto.creada_local_en),
            recibida_en=ahora,
            aceptada_en=resultado.aceptada_en,
            referencia_horaria_id=dto.referencia_horaria_id,
            hash_solicitud=digest,
            solicitud=dto.model_dump(mode="json"),
            estado=resultado.estado,
            codigo=resultado.codigo,
            detalle=resultado.detalle,
            resultado=resultado.model_dump(mode="json"),
            recurso_id=pedido.id,
            revision=1,
        )
        self.db.add(op_rec)
        await self.db.commit()
        return resultado


    async def consultarOperacion(
        self, usuario: Usuario, operacion_id: uuid.UUID
    ) -> ResultadoOperacionDTO:
        if not usuario.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario sin empresa asignada",
            )
        if es_admin(usuario):
            op = await self.sinc_repo.buscarOperacionPorUuid(
                operacion_id, empresa_id=usuario.empresa_id
            )
        else:
            op = await self.sinc_repo.buscarOperacionPorActor(
                operacion_id, usuario.id, usuario.empresa_id
            )
        if op is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Operacion no encontrada",
            )
        return ResultadoOperacionDTO.model_validate(op.resultado)
