"""Modelos del paquete Identidad y Empresas (CU01, CU02 / previstos CU26, CU27).

Define Rol, Usuario, Cliente y Empleado para autenticación y control de acceso.
"""
import uuid
from backend.app.core.reloj import utcnow
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.app.core.database import Base


class Rol(Base):
    __tablename__ = "roles"
    __table_args__ = {"schema": "seguridad"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(50), nullable=False, unique=True)
    descripcion = Column(Text, nullable=True)
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    usuarios = relationship("Usuario", back_populates="rol")


class Usuario(Base):
    __tablename__ = "usuarios"
    __table_args__ = {"schema": "seguridad"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rol_id = Column(UUID(as_uuid=True), ForeignKey("seguridad.roles.id"), nullable=False)
    nombres = Column(String(100), nullable=False)
    apellidos = Column(String(100), nullable=False)
    correo_electronico = Column(String(160), nullable=False, unique=True, index=True)
    contrasenia_hash = Column(String(255), nullable=False)
    telefono = Column(String(30), nullable=True)
    estado = Column(String(20), nullable=False, default="ACTIVO")
    creado_en = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    actualizado_en = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    rol = relationship("Rol", back_populates="usuarios")
    cliente = relationship("Cliente", back_populates="usuario", uselist=False, cascade="all, delete-orphan")
    empleado = relationship("Empleado", back_populates="usuario", uselist=False, cascade="all, delete-orphan")

    @property
    def nombre_completo(self) -> str:
        return f"{self.nombres} {self.apellidos}".strip()


class Cliente(Base):
    __tablename__ = "clientes"
    __table_args__ = {"schema": "seguridad"}

    usuario_id = Column(UUID(as_uuid=True), ForeignKey("seguridad.usuarios.id", ondelete="CASCADE"), primary_key=True)
    direccion_referencia = Column(Text, nullable=True)
    fecha_nacimiento = Column(Date, nullable=True)
    preferencias = Column(JSONB, nullable=False, default=dict)

    usuario = relationship("Usuario", back_populates="cliente")


class Empleado(Base):
    __tablename__ = "empleados"
    __table_args__ = {"schema": "seguridad"}

    usuario_id = Column(UUID(as_uuid=True), ForeignKey("seguridad.usuarios.id", ondelete="CASCADE"), primary_key=True)
    sucursal_id = Column(UUID(as_uuid=True), ForeignKey("organizacion.sucursales.id"), nullable=True)
    cargo = Column(String(80), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)

    usuario = relationship("Usuario", back_populates="empleado")
