"""Modelos del paquete Catálogo (CU05, CU06, CU22 / previsto CU28).

Define categorías, tallas, colores, temporadas, colecciones, productos,
variantes, imágenes de producto y promociones.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Boolean, SmallInteger, Integer, Numeric,
    ForeignKey, Date, DateTime, UniqueConstraint, PrimaryKeyConstraint,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.app.core.database import Base
from backend.app.core.reloj import utcnow


def _ahora_utc():
    return datetime.now(timezone.utc)


class Categoria(Base):
    __tablename__ = "categorias"
    __table_args__ = (
        UniqueConstraint("categoria_padre_id", "nombre", name="uq_categoria_padre_nombre"),
        {"schema": "catalogo"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    categoria_padre_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.categorias.id"), nullable=True)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(Text, nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    subcategorias = relationship("Categoria", backref="categoria_padre", remote_side=[id])
    productos = relationship("Producto", back_populates="categoria")


class Talla(Base):
    __tablename__ = "tallas"
    __table_args__ = {"schema": "catalogo"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(30), nullable=False, unique=True)
    orden = Column(SmallInteger, nullable=False, default=0)
    activo = Column(Boolean, nullable=False, default=True)

    variantes = relationship("VarianteProducto", back_populates="talla")


class Color(Base):
    __tablename__ = "colores"
    __table_args__ = {"schema": "catalogo"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(60), nullable=False, unique=True)
    codigo_hex = Column(String(7), nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    variantes = relationship("VarianteProducto", back_populates="color")


class Temporada(Base):
    __tablename__ = "temporadas"
    __table_args__ = {"schema": "catalogo"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False, unique=True)
    fecha_inicio = Column(Date, nullable=True)
    fecha_fin = Column(Date, nullable=True)
    activa = Column(Boolean, nullable=False, default=True)


class Coleccion(Base):
    __tablename__ = "colecciones"
    __table_args__ = {"schema": "catalogo"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(100), nullable=False, unique=True)
    descripcion = Column(Text, nullable=True)
    activa = Column(Boolean, nullable=False, default=True)


class Proveedor(Base):
    __tablename__ = "proveedores"
    __table_args__ = {"schema": "catalogo"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    razon_social = Column(String(180), nullable=False)
    nit = Column(String(40), unique=True, nullable=True)
    contacto = Column(String(160), nullable=True)
    telefono = Column(String(30), nullable=True)
    correo_electronico = Column(String(160), nullable=True)
    direccion = Column(Text, nullable=True)
    convenio = Column(Text, nullable=True)
    activo = Column(Boolean, nullable=False, default=True)

    productos = relationship("Producto", back_populates="proveedor_principal")


class Producto(Base):
    __tablename__ = "productos"
    __table_args__ = {"schema": "catalogo"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    categoria_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.categorias.id"), nullable=True)
    proveedor_principal_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.proveedores.id"), nullable=True)
    nombre = Column(String(180), nullable=False)
    descripcion = Column(Text, nullable=True)
    genero = Column(String(30), nullable=True)
    marca = Column(String(100), nullable=True)
    precio_base = Column(Numeric(12, 2), nullable=False, default=0)
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    actualizado_en = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    categoria = relationship("Categoria", back_populates="productos")
    proveedor_principal = relationship("Proveedor", back_populates="productos")
    variantes = relationship("VarianteProducto", back_populates="producto", cascade="all, delete-orphan")
    imagenes = relationship("ImagenProducto", back_populates="producto", cascade="all, delete-orphan")


class ImagenProducto(Base):
    __tablename__ = "imagenes_producto"
    __table_args__ = {"schema": "catalogo"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.productos.id", ondelete="CASCADE"), nullable=False)
    enlace_imagen = Column(Text, nullable=False)
    texto_alternativo = Column(String(180), nullable=True)
    orden = Column(SmallInteger, nullable=False, default=0)
    es_principal = Column(Boolean, nullable=False, default=False)

    producto = relationship("Producto", back_populates="imagenes")


class ProductoTemporada(Base):
    __tablename__ = "producto_temporada"
    __table_args__ = (
        PrimaryKeyConstraint("producto_id", "temporada_id"),
        {"schema": "catalogo"},
    )

    producto_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.productos.id", ondelete="CASCADE"), nullable=False)
    temporada_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.temporadas.id"), nullable=False)


class ProductoColeccion(Base):
    __tablename__ = "producto_coleccion"
    __table_args__ = (
        PrimaryKeyConstraint("producto_id", "coleccion_id"),
        {"schema": "catalogo"},
    )

    producto_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.productos.id", ondelete="CASCADE"), nullable=False)
    coleccion_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.colecciones.id"), nullable=False)


class VarianteProducto(Base):
    __tablename__ = "variantes_producto"
    __table_args__ = (
        UniqueConstraint("producto_id", "talla_id", "color_id", name="uq_variante_prod_talla_color"),
        {"schema": "catalogo"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    producto_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.productos.id", ondelete="CASCADE"), nullable=False)
    talla_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.tallas.id"), nullable=False)
    color_id = Column(UUID(as_uuid=True), ForeignKey("catalogo.colores.id"), nullable=False)
    sku = Column(String(80), nullable=False, unique=True, index=True)
    codigo_barras = Column(String(80), unique=True, nullable=True)
    precio = Column(Numeric(12, 2), nullable=False)
    peso_gramos = Column(Integer, nullable=True)
    costo_promedio = Column(Numeric(12, 2), nullable=False, default=0)
    costo_ultimo = Column(Numeric(12, 2), nullable=False, default=0)
    recurso_prueba_virtual = Column(Text, nullable=True)
    activa = Column(Boolean, nullable=False, default=True)

    producto = relationship("Producto", back_populates="variantes")
    talla = relationship("Talla", back_populates="variantes")
    color = relationship("Color", back_populates="variantes")


class Promocion(Base):
    """catalogo.promociones — CU22. Tipo PORCENTAJE (0-100) o MONTO_FIJO."""

    __tablename__ = "promociones"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('PORCENTAJE','MONTO_FIJO')",
            name="ck_promociones_tipo",
        ),
        CheckConstraint("valor >= 0", name="ck_promociones_valor_nneg"),
        CheckConstraint(
            "(tipo <> 'PORCENTAJE') OR (valor <= 100)",
            name="ck_promociones_porcentaje_max",
        ),
        CheckConstraint(
            "vigencia_fin IS NULL OR vigencia_inicio IS NULL OR vigencia_inicio <= vigencia_fin",
            name="ck_promociones_vigencia_coherente",
        ),
        {"schema": "catalogo"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = Column(String(40), nullable=False, unique=True)
    nombre = Column(String(180), nullable=False)
    descripcion = Column(Text, nullable=True)
    tipo = Column(String(20), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    activa = Column(Boolean, nullable=False, default=True)
    vigencia_inicio = Column(DateTime(timezone=True), nullable=True)
    vigencia_fin = Column(DateTime(timezone=True), nullable=True)
    creada_en = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)
    actualizada_en = Column(
        DateTime(timezone=True), default=_ahora_utc, onupdate=_ahora_utc, nullable=False
    )
    creada_por = Column(UUID(as_uuid=True), ForeignKey("seguridad.usuarios.id"), nullable=True)

    variantes = relationship(
        "PromocionVariante", back_populates="promocion", cascade="all, delete-orphan"
    )


class PromocionVariante(Base):
    """catalogo.promocion_variante — asociación promo <-> variante (CU22)."""

    __tablename__ = "promocion_variante"
    __table_args__ = {"schema": "catalogo"}

    promocion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("catalogo.promociones.id", ondelete="CASCADE"),
        primary_key=True,
    )
    variante_id = Column(
        UUID(as_uuid=True),
        ForeignKey("catalogo.variantes_producto.id", ondelete="CASCADE"),
        primary_key=True,
    )
    creada_en = Column(DateTime(timezone=True), default=_ahora_utc, nullable=False)

    promocion = relationship("Promocion", back_populates="variantes")
