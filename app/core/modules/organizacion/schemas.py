"""Esquemas DTO del paquete organizacional (CU03 / RF03)."""
import uuid
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class CiudadCrearDTO(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre de la ciudad")


class CiudadDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    activo: bool


class SucursalCrearDTO(BaseModel):
    ciudad_id: uuid.UUID = Field(..., description="ID de la ciudad a la que pertenece la sucursal")
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre de la sucursal")
    direccion: str = Field(..., min_length=3, description="Dirección física de la sucursal")
    telefono: Optional[str] = Field(None, max_length=30, description="Teléfono de contacto")
    numero_anillo: Optional[int] = Field(None, ge=1, le=10, description="Número de anillo de ubicación (1 a 10)")
    tarifa_base_delivery: Decimal = Field(default=Decimal("15.00"), ge=0, description="Tarifa base de delivery en Bs")
    incremento_anillo_delivery: Decimal = Field(default=Decimal("3.00"), ge=0, description="Incremento por diferencia de anillo en Bs")
    anillo_minimo_delivery: int = Field(default=1, ge=1, le=10, description="Anillo mínimo atendido")
    anillo_maximo_delivery: int = Field(default=10, ge=1, le=10, description="Anillo máximo atendido")
    delivery_activo: bool = Field(default=True, description="Indica si ofrece servicio de delivery")


class ConfigurarTarifasDeliveryDTO(BaseModel):
    tarifa_base_delivery: Decimal = Field(..., ge=0, description="Nueva tarifa base de delivery en Bs")
    incremento_anillo_delivery: Decimal = Field(..., ge=0, description="Nuevo incremento por anillo en Bs")
    anillo_minimo_delivery: Optional[int] = Field(None, ge=1, le=10, description="Anillo mínimo")
    anillo_maximo_delivery: Optional[int] = Field(None, ge=1, le=10, description="Anillo máximo")
    delivery_activo: Optional[bool] = Field(None, description="Habilitar/deshabilitar delivery")


class ConfigurarAdelantoDTO(BaseModel):
    adelanto_activo: bool = Field(..., description="Activa el adelanto en la sucursal")
    modalidad_adelanto: Optional[str] = Field(None, description="MONTO_FIJO o PORCENTAJE (exigida si activo)")
    valor_adelanto: Optional[Decimal] = Field(None, description="Monto fijo o porcentaje 0-100 (exigido si activo)")


class SucursalDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    ciudad_id: uuid.UUID
    ciudad_nombre: Optional[str] = None
    nombre: str
    direccion: str
    telefono: Optional[str] = None
    numero_anillo: Optional[int] = None
    tarifa_base_delivery: Decimal
    incremento_anillo_delivery: Decimal
    anillo_minimo_delivery: int
    anillo_maximo_delivery: int
    delivery_activo: bool
    activa: bool
    adelanto_activo: bool = False
    modalidad_adelanto: Optional[str] = None
    valor_adelanto: Decimal = Decimal("0")
