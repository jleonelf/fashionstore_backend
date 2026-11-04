"""Esquemas DTO para sincronización offline (CU04 / C34)."""
import uuid
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ReferenciaHorariaDTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "referencia_horaria_id": "50000000-0000-4000-8000-000000000001",
                "emitida_en": "2026-10-18T09:59:00-04:00",
                "vence_en": "2026-10-18T17:59:00-04:00",
            }
        },
    )

    referencia_horaria_id: uuid.UUID = Field(..., description="UUID emitido por el servidor central")
    emitida_en: datetime = Field(..., description="Instante UTC en que se emitió la referencia")
    vence_en: datetime = Field(..., description="Fin de vigencia para crear operaciones offline (8 horas desde emisión)")



class ReferenciaHorariaCrearDTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "dispositivo_id": "40000000-0000-4000-8000-000000000001",
                "hora_local_en": "2026-11-01T10:00:00-04:00",
            }
        },
    )

    dispositivo_id: uuid.UUID = Field(..., description="UUID del dispositivo móvil o cliente web")
    hora_local_en: datetime = Field(..., description="Hora civil del dispositivo emisor, con offset explícito")

    @field_validator("hora_local_en")
    @classmethod
    def validar_con_offset(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("hora_local_en requiere zona horaria con offset explícito (-04:00)")
        offset = v.utcoffset()
        if offset is None or offset.total_seconds() != -14400:
            raise ValueError("hora_local_en debe incluir el offset de Bolivia (-04:00)")
        return v


class ReferenciaHorariaDetalleDTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "referencia_horaria_id": "50000000-0000-4000-8000-000000000001",
                "empresa_id": "20000000-0000-4000-8000-000000000001",
                "usuario_id": "30000000-0000-4000-8000-000000000001",
                "dispositivo_id": "40000000-0000-4000-8000-000000000001",
                "hora_central_en": "2026-11-01T10:00:00-04:00",
                "valida_hasta": "2026-11-01T18:00:00-04:00",
                "tolerancia_segundos": 300,
                "politica_version": 1,
            }
        },
    )

    referencia_horaria_id: uuid.UUID
    empresa_id: uuid.UUID
    usuario_id: uuid.UUID
    dispositivo_id: uuid.UUID
    hora_central_en: datetime
    valida_hasta: datetime
    tolerancia_segundos: int = Field(default=300, description="Tolerancia de reloj en segundos (5 min)")
    politica_version: int = Field(default=1, description="Versión de política temporal")


class OperacionLineaDTO(BaseModel):
    variante_id: uuid.UUID = Field(..., description="UUID de la variante solicitada")
    cantidad: int = Field(..., gt=0, description="Cantidad solicitada (> 0)")


class OperacionDatosReservaDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sucursal_id: uuid.UUID = Field(..., description="Sucursal destino de la reserva")
    visita_en: datetime = Field(..., description="Fecha/hora aproximada de visita (obligatoria; no sustituye el origen del plazo)")
    lineas: List[OperacionLineaDTO] = Field(..., min_length=1, description="Líneas de prendas a reservar")


class OperacionDTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "version_esquema": 1,
                "operacion_id": "10000000-0000-4000-8000-000000000001",
                "tipo": "SOLICITAR_RESERVA",
                "creada_local_en": "2026-10-18T10:00:00-04:00",
                "empresa_id": "20000000-0000-4000-8000-000000000001",
                "usuario_id": "30000000-0000-4000-8000-000000000001",
                "dispositivo_id": "40000000-0000-4000-8000-000000000001",
                "secuencia_local": 1,
                "referencia_horaria_id": "50000000-0000-4000-8000-000000000001",
                "datos": {
                    "sucursal_id": "60000000-0000-4000-8000-000000000001",
                    "visita_en": "2026-10-18T14:00:00-04:00",
                    "lineas": [
                        {"variante_id": "70000000-0000-4000-8000-000000000001", "cantidad": 1}
                    ],
                },
            }
        },
    )

    version_esquema: Literal[1] = Field(..., description="Versión del esquema de sincronización (solo 1 en esta entrega)")
    operacion_id: uuid.UUID = Field(..., description="UUID inmutable de la operación generado localmente")
    tipo: Literal["SOLICITAR_RESERVA", "SOLICITAR_COMPRA", "REGISTRAR_VENTA_CAJA"] = Field(
        ..., description="Tipo de operación; en esta entrega únicamente SOLICITAR_RESERVA"
    )
    creada_local_en: datetime = Field(..., description="Fecha y hora de creación local en el dispositivo")
    empresa_id: uuid.UUID = Field(..., description="UUID de la empresa contratante")
    usuario_id: uuid.UUID = Field(..., description="UUID del usuario que creó la operación localmente")
    dispositivo_id: uuid.UUID = Field(..., description="UUID del dispositivo emisor")
    secuencia_local: int = Field(..., ge=1, description="Secuencia local monótona en el dispositivo")
    referencia_horaria_id: Optional[uuid.UUID] = Field(
        None, description="UUID de la referencia horaria emitida previamente por el servidor"
    )
    datos: OperacionDatosReservaDTO = Field(..., description="Datos específicos de la operación de reserva")


class ResultadoOperacionDTO(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "operacion_id": "10000000-0000-4000-8000-000000000001",
                "estado": "ACEPTADA",
                "codigo": "OK",
                "recibida_en": "2026-10-18T10:02:00-04:00",
                "aceptada_en": "2026-10-18T10:02:00-04:00",
                "recurso_id": "80000000-0000-4000-8000-000000000001",
                "vence_en": "2026-10-19T10:00:00-04:00",
                "detalle": "Reserva aceptada",
            }
        },
    )

    operacion_id: uuid.UUID
    estado: Literal[
        "ACEPTADA",
        "RECHAZADA",
        "REQUIERE_ACEPTACION_PRECIO",
        "PENDIENTE_PAGO",
        "REGISTRADA_CENTRAL",
        "CONCILIACION_REQUERIDA",
        "CONFLICTO",
    ]
    codigo: Literal[
        "OK",
        "SIN_STOCK",
        "PRECIO_CAMBIADO",
        "SOLICITUD_VENCIDA",
        "TIEMPO_INCOHERENTE",
        "PLAN_NO_HABILITADO",
        "CUPO_INSUFICIENTE",
        "TASA_NO_VIGENTE",
        "OPERACION_MODIFICADA",
        "PAGO_EN_VERIFICACION",
    ]
    recibida_en: datetime
    detalle: str
    aceptada_en: Optional[datetime] = None
    vence_en: Optional[datetime] = None
    recurso_id: Optional[uuid.UUID] = None
    revision: Optional[int] = 1


class ConflictoOperacionModificadaDTO(BaseModel):
    codigo: str = "OPERACION_MODIFICADA"
    detalle: str = "operacion_id reutilizado con contenido distinto"


class ErrorOperacionModificadaDTO(BaseModel):
    """Envoltorio HTTP real de un 409 emitido con HTTPException."""

    detail: ConflictoOperacionModificadaDTO
