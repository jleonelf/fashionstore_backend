"""Schemas del módulo Ventas, Pagos, Carrito y Entregas (CU11, CU13, CU14, CU15, CU16, CU23)."""
import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

MetodoCaja = Literal["EFECTIVO", "TARJETA_CAJA", "QR_CAJA", "TRANSFERENCIA"]
EstadoPagoStripe = Literal["PENDIENTE", "APROBADO", "RECHAZADO", "ANULADO"]
ModalidadEntrega = Literal["RECOJO", "DELIVERY"]
CanalDigital = Literal["WEB", "MOVIL"]


class AdelantoCrearDTO(BaseModel):
    reserva_id: uuid.UUID = Field(..., description="Reserva sobre la que se registra el adelanto")
    metodo: MetodoCaja = Field(..., description="Unico metodo de caja por pago")


class PagoDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    contexto: str
    reserva_id: Optional[uuid.UUID] = None
    venta_id: Optional[uuid.UUID] = None
    metodo: str
    tipo_pago: Optional[str] = None
    modalidad_adelanto: Optional[str] = None
    monto: Decimal
    no_reembolsable: bool
    estado: str
    referencia_externa: Optional[str] = None
    pagado_en: Optional[datetime] = None
    clave_idempotencia: Optional[uuid.UUID] = None


class PagoListaDTO(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[PagoDTO]


class ItemVentaDTO(BaseModel):
    detalle_reserva_id: Optional[uuid.UUID] = Field(
        None, description="Linea de reserva (obligatorio en venta desde reserva)"
    )
    variante_id: uuid.UUID = Field(..., description="Variante vendida")
    cantidad: int = Field(..., description="Cantidad (>0, validado en servicio -> 400)")


class VentaPresencialCrearDTO(BaseModel):
    reserva_id: Optional[uuid.UUID] = Field(None, description="Reserva ATENDIDA origen (venta directa si ausente)")
    sucursal_id: uuid.UUID = Field(..., description="Sucursal y caja de la venta")
    cliente_id: Optional[uuid.UUID] = Field(None, description="Cliente (directa anonima si ausente y sin reserva)")
    metodo: MetodoCaja = Field(..., description="Unico metodo de caja por pago")
    items: List[ItemVentaDTO] = Field(..., description="Al menos un item (validado en servicio -> 400)")


class DetalleVentaDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    detalle_reserva_id: Optional[uuid.UUID] = None
    variante_id: uuid.UUID
    cantidad: int
    precio_unitario: Decimal
    descuento: Decimal
    promocion_id: Optional[uuid.UUID] = Field(
        None, description="Promoción aplicada y congelada al vender"
    )
    costo_promedio: Optional[Decimal] = Field(
        None, description="Costo congelado; solo roles autorizados (ADMIN/ENCARGADO)"
    )


class VentaDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    numero: str
    cliente_id: Optional[uuid.UUID] = None
    reserva_id: Optional[uuid.UUID] = None
    sucursal_id: uuid.UUID
    cajero_id: Optional[uuid.UUID] = None
    canal: str
    estado: str
    subtotal: Decimal
    descuento: Decimal
    adelanto_descontado: Decimal
    costo_entrega: Decimal
    total: Decimal
    creada_en: datetime
    confirmada_en: Optional[datetime] = None
    expira_en: Optional[datetime] = Field(
        None, description="Vencimiento del compromiso de stock digital (60 min)"
    )
    detalles: List[DetalleVentaDTO] = Field(default_factory=list)


class ComprobanteDTO(VentaDTO):
    reserva_codigo: Optional[str] = None
    sucursal_nombre: Optional[str] = None
    cajero_nombre: Optional[str] = None
    pagos: List[PagoDTO] = Field(default_factory=list)


class HistorialComprasDTO(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[VentaDTO]


class LineaAgregarDTO(BaseModel):
    variante_id: uuid.UUID
    cantidad: int = Field(..., gt=0, le=99)


class LineaActualizarDTO(BaseModel):
    cantidad: int = Field(..., gt=0, le=99)


class LineaCarritoDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    variante_id: uuid.UUID
    cantidad: int
    precio_unitario: Decimal = Decimal("0")
    descuento_unitario: Decimal = Decimal("0")
    promocion_id: Optional[uuid.UUID] = None
    subtotal: Decimal = Decimal("0")


class CarritoDTO(BaseModel):
    id: uuid.UUID
    cliente_id: uuid.UUID
    canal: str
    estado: str
    creada_en: datetime
    actualizada_en: datetime
    lineas: List[LineaCarritoDTO] = Field(default_factory=list)
    subtotal: Decimal = Decimal("0")
    descuento_total: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class CoberturaSucursalDTO(BaseModel):
    sucursal_id: uuid.UUID
    sucursal_nombre: str
    cubre_todo: bool
    faltantes: List[uuid.UUID] = Field(default_factory=list)


class CoberturaDTO(BaseModel):
    sucursales: List[CoberturaSucursalDTO]


class CheckoutCrearDTO(BaseModel):
    sucursal_id: uuid.UUID = Field(..., description="Única sucursal de origen del inventario")
    canal: CanalDigital = Field(..., description="WEB o MOVIL")
    modalidad: ModalidadEntrega = Field(..., description="RECOJO o DELIVERY")
    direccion: Optional[str] = Field(None, description="Obligatoria en DELIVERY")
    anillo_destino: Optional[int] = Field(None, ge=1, le=12)


class CheckoutRespuestaDTO(BaseModel):
    venta_id: uuid.UUID
    numero: str
    estado: str
    total: Decimal
    expira_en: datetime
    pedido_entrega_id: uuid.UUID


class IntencionCrearDTO(BaseModel):
    venta_id: uuid.UUID = Field(..., description="Venta PENDIENTE_PAGO del checkout digital")


class IntencionDTO(BaseModel):
    payment_intent_id: str
    venta_id: uuid.UUID
    monto: Decimal
    moneda: str
    estado: str
    client_secret: Optional[str] = None


class EstadoPagoDTO(BaseModel):
    venta_id: uuid.UUID
    estado_venta: str
    estado_pago: str
    payment_intent_id: Optional[str] = None
    monto: Decimal
    expira_en: Optional[datetime] = None


class CotizacionDTO(BaseModel):
    sucursal_id: uuid.UUID
    anillo_sucursal: Optional[int] = None
    anillo_destino: int
    tarifa_base: Decimal
    incremento_anillo: Decimal
    costo_entrega: Decimal


class PedidoDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    venta_id: uuid.UUID
    sucursal_id: uuid.UUID
    modalidad: str
    estado: str
    anillo_sucursal: Optional[int] = None
    anillo_destino: Optional[int] = None
    direccion: Optional[str] = None
    tarifa_base: Decimal
    incremento_anillo: Decimal
    costo_entrega: Decimal
    codigo_recojo: Optional[str] = None
    creada_en: datetime
    puede_cancelar: bool = False
    puede_transicionar: bool = False
    siguiente_estado: Optional[
        Literal["PREPARADO", "LISTO_RECOJO", "EN_REPARTO", "RECOGIDO", "ENTREGADO"]
    ] = None


class PedidoListaDTO(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[PedidoDTO]


class TransicionPedidoDTO(BaseModel):
    estado: Literal[
        "SOLICITADO", "PREPARADO", "LISTO_RECOJO", "EN_REPARTO",
        "RECOGIDO", "ENTREGADO", "CANCELADO",
    ]


__all__ = [
    "MetodoCaja",
    "EstadoPagoStripe",
    "ModalidadEntrega",
    "CanalDigital",
    "AdelantoCrearDTO",
    "PagoDTO",
    "PagoListaDTO",
    "ItemVentaDTO",
    "VentaPresencialCrearDTO",
    "DetalleVentaDTO",
    "VentaDTO",
    "ComprobanteDTO",
    "HistorialComprasDTO",
    "LineaAgregarDTO",
    "LineaActualizarDTO",
    "LineaCarritoDTO",
    "CarritoDTO",
    "CoberturaSucursalDTO",
    "CoberturaDTO",
    "CheckoutCrearDTO",
    "CheckoutRespuestaDTO",
    "IntencionCrearDTO",
    "IntencionDTO",
    "EstadoPagoDTO",
    "CotizacionDTO",
    "PedidoDTO",
    "PedidoListaDTO",
    "TransicionPedidoDTO",
]
