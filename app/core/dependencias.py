import uuid
from typing import List, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.modules.identidad_empresas.models import Usuario

security = HTTPBearer(auto_error=False)

async def get_usuario_actual(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Usuario:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado: se requiere token Bearer",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido: sub ausente")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido: sub no es UUID")

    query = (
        select(Usuario)
        .options(selectinload(Usuario.rol), selectinload(Usuario.empleado), selectinload(Usuario.cliente))
        .where(Usuario.id == uid)
    )
    result = await db.execute(query)
    usuario = result.scalars().first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario del token no existe")
    if usuario.estado != "ACTIVO":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cuenta inactiva")
    return usuario

def require_roles(*roles_permitidos: str):
    roles_upper = [r.upper() for r in roles_permitidos]
    async def _check(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
        rol_actual = (usuario.rol.nombre if usuario.rol else "").upper()
        if rol_actual not in roles_upper:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso denegado: se requiere uno de los roles {roles_upper} (tu rol: {rol_actual})"
            )
        return usuario
    return _check

async def get_usuario_opcional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[Usuario]:
    if credentials is None:
        return None
    try:
        return await get_usuario_actual(credentials, db)
    except HTTPException:
        return None

def get_sucursal_del_usuario(usuario: Usuario) -> Optional[uuid.UUID]:
    if usuario.empleado and usuario.empleado.sucursal_id:
        return usuario.empleado.sucursal_id
    return None
