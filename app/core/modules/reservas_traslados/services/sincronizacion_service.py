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
from decimal import Decimal
from functools import partial
from typing import Optional

from fastapi import HTTPException, status
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

CODIGO_ALFABETO = string.ascii_uppercase + string.digits


def calcular_hash_operacion(dto: OperacionDTO) -> str:
    """Calcula el hash SHA-256 canónico de los campos inmutables de la operación."""
    lineas_ordenadas = sorted(
        [{"cantidad": l.cantidad, "variante_id": str(l.variante_id)} for l in dto.datos.lineas],
        key=lambda x: x["variante_id"],
    )
    datos_dict = {
        "lineas": lineas_ordenadas,
        "sucursal_id": str(dto.datos.sucursal_id),
        "visita_en": dto.datos.visita_en.isoformat() if dto.datos.visita_en else None,
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
        if dto.tipo != "SOLICITAR_RESERVA":
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

        # Las lineas duplicadas son un error de forma (400), no un rechazo
        # comercial: nunca deben llegar a apartar stock ni violar el UNIQUE.
        validar_lineas_reserva(dto.datos.lineas)

        digest = calcular_hash_operacion(dto)

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
