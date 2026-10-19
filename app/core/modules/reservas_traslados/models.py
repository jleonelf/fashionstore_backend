"""Modelos de Dominio: Reservas y Traslados (CU08, CU09, CU10, CU24)."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Numeric,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, ENUM
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


def _ahora_utc():
    return datetime.now(timezone.utc)


EstadoReserva = ENUM(
    "PENDIENTE_TRASLADO",
    "PENDIENTE",
    "PREPARADA",
    "ATENDIDA",
    "COMPLETADA",
    "CANCELADA",
    "VENCIDA",
    name="estado_reserva",
    schema="comercial",
    create_type=False,
)

ESTADOS_LINEA_RESERVA = (
    "PENDIENTE_TRASLADO",
    "RESERVADA",
    "RECHAZADA",
    "VENDIDA_PARCIAL",
    "VENDIDA",
    "LIBERADA",
)

EstadoTraslado = ENUM(
    "SOLICITADO",
    "APROBADO",
    "RECHAZADO",
    "DESPACHADO",
    "RECIBIDO",
    "CANCELADO",
    name="estado_traslado",
    schema="inventario",
    create_type=False,
)


class Reserva(Base):
    __tablename__ = "reservas"
    __table_args__ = (
        CheckConstraint(
            "codigo LIKE 'FS-%'",
            name="ck_reservas_codigo_formato",
        ),
        {"schema": "comercial"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cliente_id = Column(UUID(as_uuid=True), ForeignKey("seguridad.clientes.usuario_id"), nullable=False)
    sucursal_destino_id = Column(UUID(as_uuid=True), ForeignKey("organizacion.sucursales.id"), nullable=False)
    codigo = Column(String(50), nullable=False, unique=True)
    estado = Column(EstadoReserva, nullable=False, default="PENDIENTE")
    fecha_creacion = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)
    fecha_visita = Column(DateTime(timezone=True), nullable=True)
    vence_en = Column(DateTime(timezone=True), nullable=False)
    observacion = Column(Text, nullable=True)
    adelanto_modalidad = Column(String(20), nullable=True)
    adelanto_valor = Column(Numeric(12, 2), nullable=True)
    adelanto_monto = Column(Numeric(12, 2), nullable=True)
    preparada_en = Column(DateTime(timezone=True), nullable=True)
    atendida_en = Column(DateTime(timezone=True), nullable=True)
    preparada_por = Column(UUID(as_uuid=True), ForeignKey("seguridad.usuarios.id"), nullable=True)
    atendida_por = Column(UUID(as_uuid=True), ForeignKey("seguridad.usuarios.id"), nullable=True)
    clave_idempotencia = Column(UUID(as_uuid=True), nullable=True, unique=True)
    hash_solicitud = Column(Text, nullable=True)

    detalles = relationship("DetalleReserva", back_populates="reserva", cascade="all, delete-orphan")


class DetalleReserva(Base):
    __tablename__ = "detalles_reserva"
    __table_args__ = (
        UniqueConstraint("reserva_id", "variante_id", name="uq_detalles_reserva_reserva_variante"),
        CheckConstraint("cantidad_solicitada > 0", name="ck_detalle_reserva_solicitada_pos"),
        CheckConstraint("cantidad_reservada >= 0", name="ck_detalle_reserva_reservada_nneg"),
        CheckConstraint("cantidad_pendiente_traslado >= 0", name="ck_detalle_reserva_pendtras_nneg"),
        CheckConstraint("cantidad_vendida >= 0", name="ck_detalle_reserva_vendida_nneg"),
        CheckConstraint("cantidad_liberada >= 0", name="ck_detalle_reserva_liberada_nneg"),
        CheckConstraint(
            "cantidad_reservada + cantidad_pendiente_traslado + cantidad_vendida + cantidad_liberada <= cantidad_solicitada",
            name="ck_detalle_reserva_cantidades_consistentes",
        ),
        {"schema": "comercial"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reserva_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comercial.reservas.id", ondelete="CASCADE"),
        nullable=False,
    )
    variante_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.variantes_producto.id"), nullable=False)
    cantidad_solicitada = Column(Integer, nullable=False)
    cantidad_reservada = Column(Integer, nullable=False, default=0)
    cantidad_pendiente_traslado = Column(Integer, nullable=False, default=0)
    cantidad_vendida = Column(Integer, nullable=False, default=0)
    cantidad_liberada = Column(Integer, nullable=False, default=0)
    estado_linea = Column(String(30), nullable=False, default="RESERVADA")

    reserva = relationship("Reserva", back_populates="detalles")


class Traslado(Base):
    __tablename__ = "traslados"
    __table_args__ = (
        CheckConstraint(
            "sucursal_origen_id <> sucursal_destino_id",
            name="ck_traslados_origen_destino_distintos",
        ),
        {"schema": "inventario"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reserva_id = Column(UUID(as_uuid=True), ForeignKey("comercial.reservas.id"), nullable=True)
    sucursal_origen_id = Column(UUID(as_uuid=True), ForeignKey("organizacion.sucursales.id"), nullable=False)
    sucursal_destino_id = Column(UUID(as_uuid=True), ForeignKey("organizacion.sucursales.id"), nullable=False)
    estado = Column(EstadoTraslado, nullable=False, default="SOLICITADO")
    solicitado_por_id = Column(UUID(as_uuid=True), ForeignKey("seguridad.usuarios.id"), nullable=False)
    aprobado_por_id = Column(UUID(as_uuid=True), ForeignKey("seguridad.usuarios.id"), nullable=True)
    fecha_solicitud = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)
    fecha_aprobacion = Column(DateTime(timezone=True), nullable=True)
    fecha_despacho = Column(DateTime(timezone=True), nullable=True)
    fecha_recepcion = Column(DateTime(timezone=True), nullable=True)
    motivo_rechazo = Column(Text, nullable=True)
    clave_idempotencia = Column(UUID(as_uuid=True), nullable=True, unique=True)
    hash_solicitud = Column(Text, nullable=True)

    detalles = relationship("DetalleTraslado", back_populates="traslado", cascade="all, delete-orphan")


class DetalleTraslado(Base):
    __tablename__ = "detalles_traslado"
    __table_args__ = (
        UniqueConstraint("traslado_id", "variante_id", name="uq_detalles_traslado_traslado_variante"),
        CheckConstraint("cantidad > 0", name="ck_detalle_traslado_cantidad_pos"),
        {"schema": "inventario"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    traslado_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inventario.traslados.id", ondelete="CASCADE"),
        nullable=False,
    )
    detalle_reserva_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comercial.detalles_reserva.id"),
        nullable=True,
    )
    variante_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.variantes_producto.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)

    traslado = relationship("Traslado", back_populates="detalles")
