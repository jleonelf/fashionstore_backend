"""Schemas del módulo Posventa — Devoluciones y Mermas (CU12, previstos CU33, CU34)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class DevolucionCrearDTO(BaseModel):
    detalle_venta_id: uuid.UUID = Field(..., description="Linea de venta a devolver (parcial acumulable)")
    cantidad: int = Field(..., description="Cantidad a devolver (>0, validado en servicio -> 400)")
    motivo: Optional[str] = Field(None, description="Motivo de la devolucion")


class DevolucionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    detalle_venta_id: uuid.UUID
    venta_id: uuid.UUID
    variante_id: uuid.UUID
    sucursal_id: uuid.UUID
    cantidad: int
    costo_unitario: Decimal
    motivo: Optional[str] = None
    responsable_id: Optional[uuid.UUID] = None
    fecha_hora: datetime


class MermaCrearDTO(BaseModel):
    variante_id: uuid.UUID = Field(...)
    sucursal_id: uuid.UUID = Field(...)
    cantidad: int = Field(..., description="Cantidad mermada (>0, validado en servicio -> 400)")
    causa: Optional[str] = Field(None, description="Causa documentada (obligatoria -> 400 si falta)")
    responsable_id: Optional[uuid.UUID] = Field(None, description="Responsable (por defecto quien registra)")


class MermaDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    variante_id: uuid.UUID
    sucursal_id: uuid.UUID
    cantidad: int
    costo_unitario: Decimal
    causa: Optional[str] = None
    responsable_id: Optional[uuid.UUID] = None
    fecha_hora: datetime


__all__ = [
    "DevolucionCrearDTO",
    "DevolucionDTO",
    "MermaCrearDTO",
    "MermaDTO",
]
