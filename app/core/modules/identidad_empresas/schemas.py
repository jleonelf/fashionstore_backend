"""Esquemas DTO del paquete Identidad y Empresas (CU01, CU02)."""
import uuid
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class RegistroClienteDTO(BaseModel):
    nombres: str = Field(..., min_length=2, max_length=100, description="Nombres del cliente")
    apellidos: str = Field(..., min_length=2, max_length=100, description="Apellidos del cliente")
    correo_electronico: EmailStr = Field(..., max_length=160, description="Correo electrónico único")
    contrasenia: str = Field(..., min_length=6, max_length=100, description="Contraseña en texto plano")
    telefono: Optional[str] = Field(None, max_length=30, description="Teléfono de contacto")
    direccion_referencia: Optional[str] = Field(None, description="Dirección de referencia para entregas")
    fecha_nacimiento: Optional[date] = Field(None, description="Fecha de nacimiento")
    preferencias: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Preferencias iniciales")


class LoginDTO(BaseModel):
    correo_electronico: EmailStr = Field(..., description="Correo electrónico del usuario")
    contrasenia: str = Field(..., description="Contraseña del usuario")


class UsuarioPerfilDTO(BaseModel):
    id: uuid.UUID
    nombres: str
    apellidos: str
    nombre_completo: str
    correo_electronico: str
    telefono: Optional[str] = None
    rol: str
    estado: str
    creado_en: datetime

    class Config:
        from_attributes = True


class ClientePerfilDTO(BaseModel):
    id: uuid.UUID
    usuario_id: uuid.UUID
    nombres: str
    apellidos: str
    nombre_completo: str
    correo_electronico: str
    telefono: Optional[str] = None
    rol: str
    estado: str
    direccion_referencia: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    preferencias: Dict[str, Any] = Field(default_factory=dict)
    creado_en: datetime
    sucursal_id: Optional[uuid.UUID] = None
    sucursal_nombre: Optional[str] = None
    cargo: Optional[str] = None

    class Config:
        from_attributes = True


class TokenRespuestaDTO(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: ClientePerfilDTO


class RolDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    nombre: str
    descripcion: Optional[str] = None
    activo: bool
    creado_en: datetime


class UsuarioCrearDTO(BaseModel):
    rol_id: uuid.UUID = Field(..., description="ID del rol a asignar (rol único por usuario)")
    nombres: str = Field(..., min_length=2, max_length=100, description="Nombres del usuario")
    apellidos: str = Field(..., min_length=2, max_length=100, description="Apellidos del usuario")
    correo_electronico: EmailStr = Field(..., max_length=160, description="Correo electrónico único")
    contrasenia: str = Field(..., min_length=6, max_length=100, description="Contraseña en texto plano")
    telefono: Optional[str] = Field(None, max_length=30, description="Teléfono")
    sucursal_id: Optional[uuid.UUID] = Field(None, description="Sucursal asignada (obligatoria para ENCARGADO/CAJERO)")
    cargo: Optional[str] = Field(None, max_length=80, description="Cargo del empleado (ej. Encargado de Sucursal)")


class AsignarRolDTO(BaseModel):
    rol_id: uuid.UUID = Field(..., description="Nuevo ID del rol a asignar")


class ActualizarEstadoDTO(BaseModel):
    estado: str = Field(..., pattern="^(ACTIVO|INACTIVO)$", description="Nuevo estado del usuario (ACTIVO o INACTIVO)")


class UsuarioListadoDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    rol_id: uuid.UUID
    rol_nombre: str
    nombres: str
    apellidos: str
    nombre_completo: str
    correo_electronico: str
    telefono: Optional[str] = None
    estado: str
    creado_en: datetime
    actualizado_en: datetime
    sucursal_id: Optional[uuid.UUID] = None
    sucursal_nombre: Optional[str] = None
    cargo: Optional[str] = None
