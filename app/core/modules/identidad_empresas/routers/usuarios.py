import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.core.dependencias import require_roles
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.identidad_empresas.schemas import (
    UsuarioCrearDTO,
    UsuarioListadoDTO,
    AsignarRolDTO,
    ActualizarEstadoDTO,
)
from backend.app.core.modules.identidad_empresas.services.usuario_service import UsuarioService

router = APIRouter()


@router.post(
    "",
    response_model=UsuarioListadoDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario interno/externo con rol único (CU02 / RF02)",
    description="Permite al Administrador registrar un usuario asignándole exactamente un rol maestro."
)
async def crearUsuario(
    datos_usuario: UsuarioCrearDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> UsuarioListadoDTO:
    servicio = UsuarioService(db)
    return await servicio.crear(datos_usuario)


@router.get(
    "",
    response_model=List[UsuarioListadoDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar usuarios del sistema con filtros (CU02 / RF02)",
    description="Lista todos los usuarios registrados con opción de filtrar por rol_id o estado (ACTIVO/INACTIVO)."
)
async def gestionarUsuarios(
    rol_id: Optional[uuid.UUID] = Query(None, description="Filtrar por rol"),
    estado: Optional[str] = Query(None, description="Filtrar por estado ACTIVO o INACTIVO"),
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> List[UsuarioListadoDTO]:
    servicio = UsuarioService(db)
    return await servicio.listar(rol_id=rol_id, estado=estado)


@router.patch(
    "/{usuario_id}/rol",
    response_model=UsuarioListadoDTO,
    status_code=status.HTTP_200_OK,
    summary="Asignar o cambiar rol único a un usuario (CU02 / RF02)",
    description="Modifica el rol asignado al usuario respetando la regla de rol único."
)
async def asignarRol(
    usuario_id: uuid.UUID,
    datos_rol: AsignarRolDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> UsuarioListadoDTO:
    servicio = UsuarioService(db)
    return await servicio.asignarRol(usuario_id, datos_rol.rol_id)


@router.patch(
    "/{usuario_id}/estado",
    response_model=UsuarioListadoDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar estado de usuario (CU02 / RF02)",
    description="Cambia el estado del usuario entre ACTIVO e INACTIVO."
)
async def actualizarEstadoUsuario(
    usuario_id: uuid.UUID,
    datos_estado: ActualizarEstadoDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> UsuarioListadoDTO:
    servicio = UsuarioService(db)
    return await servicio.actualizarEstado(usuario_id, datos_estado.estado)


@router.patch(
    "/{usuario_id}/desactivar",
    response_model=UsuarioListadoDTO,
    status_code=status.HTTP_200_OK,
    summary="Desactivar usuario del sistema (CU02 / RF02)",
    description="Pasa el estado del usuario a INACTIVO impidiendo su inicio de sesión."
)
async def desactivarUsuario(
    usuario_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> UsuarioListadoDTO:
    servicio = UsuarioService(db)
    return await servicio.desactivar(usuario_id)
