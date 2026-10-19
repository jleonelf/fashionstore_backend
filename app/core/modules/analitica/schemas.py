"""Schemas del módulo Analítica y Reportes (CU19, CU21, CU23, CU25, previstos CU35, CU36)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from backend.app.core.modules.ventas_pagos.schemas import HistorialComprasDTO, VentaDTO


class VentaSucursalItemDTO(BaseModel):
    id: uuid.UUID
    numero: str
    creada_en: datetime
    cliente_id: Optional[uuid.UUID] = None
    reserva_id: Optional[uuid.UUID] = None
    canal: str
    estado: str
    unidades: int
    subtotal: Decimal
    descuento: Decimal
    adelanto_descontado: Decimal
    total: Decimal
    costo_total: Optional[Decimal] = Field(None, description="Solo ADMIN/ENCARGADO")
    margen_bruto: Optional[Decimal] = Field(None, description="Solo ADMIN/ENCARGADO")


class VentasSucursalResumenDTO(BaseModel):
    total_ventas: int
    unidades: int
    monto_total: Decimal
    ticket_promedio: Decimal
    costo_total: Optional[Decimal] = None
    margen_bruto_total: Optional[Decimal] = None


class VentasSucursalDTO(BaseModel):
    total: int
    limit: int
    offset: int
    resumen: VentasSucursalResumenDTO
    items: List[VentaSucursalItemDTO]


class DashboardDTO(BaseModel):
    desde: Optional[datetime] = None
    hasta: Optional[datetime] = None
    ventas_total: int
    ingresos_total: Decimal
    margen_bruto_total: Decimal
    ticket_promedio: Decimal
    por_sucursal: List[dict] = Field(default_factory=list)
    top_productos: List[dict] = Field(default_factory=list)
    stock_critico: List[dict] = Field(default_factory=list)
    valorizacion_total: Decimal = Decimal("0")
    conversion_reservas: dict = Field(default_factory=dict)
    estados_pedidos: dict = Field(default_factory=dict)
    efectividad_promociones: dict = Field(default_factory=dict)


class ReportePedirDTO(BaseModel):
    consulta: str = Field(..., min_length=4, max_length=500)


class ReporteRespuestaDTO(BaseModel):
    funcion_usada: Literal[
        "ventasPorSucursal", "inventarioPorSucursal", "ventasPorTemporada",
        "stockCritico", "topVendidos", "efectividadReservas",
        "rotacionPorTemporada",
    ]
    parametros: dict
    datos: dict
    narrativa: str
    proveedor: str = "DETERMINISTA"


class DecisionPedirDTO(BaseModel):
    dias_ventana: int = Field(30, ge=7, le=180)
    umbral_rotacion: int = Field(2, ge=0, le=100)


class DecisionItemDTO(BaseModel):
    variante_id: uuid.UUID
    sku: str
    accion: Literal["PROMOCION", "LIQUIDACION", "TRASLADO", "REPOSICION", "MANTENER"]
    detalle: str
    stock_total: int
    ventas_periodo: int
    reposicion_sugerida: int = 0


class DecisionRespuestaDTO(BaseModel):
    items: List[DecisionItemDTO]
    proveedor: str = "DETERMINISTA"


__all__ = [
    "HistorialComprasDTO",
    "VentaSucursalItemDTO",
    "VentasSucursalResumenDTO",
    "VentasSucursalDTO",
    "DashboardDTO",
    "ReportePedirDTO",
    "ReporteRespuestaDTO",
    "DecisionPedirDTO",
    "DecisionItemDTO",
    "DecisionRespuestaDTO",
]
