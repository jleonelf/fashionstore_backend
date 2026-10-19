import uuid
from typing import Optional, List
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.modules.identidad_empresas.models import Usuario


class UsuarioRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def buscarPorCorreo(self, correo_electronico: str) -> Optional[Usuario]:
        query = (
            select(Usuario)
            .options(selectinload(Usuario.rol), selectinload(Usuario.cliente), selectinload(Usuario.empleado))
            .where(Usuario.correo_electronico == correo_electronico.strip().lower())
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def buscarPorId(self, usuario_id: uuid.UUID) -> Optional[Usuario]:
        query = (
            select(Usuario)
            .options(selectinload(Usuario.rol), selectinload(Usuario.cliente), selectinload(Usuario.empleado))
            .where(Usuario.id == usuario_id)
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def listar(self, rol_id: Optional[uuid.UUID] = None, estado: Optional[str] = None) -> List[Usuario]:
        query = select(Usuario).options(selectinload(Usuario.rol), selectinload(Usuario.cliente), selectinload(Usuario.empleado))
        if rol_id:
            query = query.where(Usuario.rol_id == rol_id)
        if estado:
            query = query.where(Usuario.estado == estado)
        query = query.order_by(Usuario.creado_en.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def crear(self, usuario: Usuario) -> Usuario:
        self.db.add(usuario)
        await self.db.flush()
        return usuario

    async def asignarRol(self, usuario_id: uuid.UUID, rol_id: uuid.UUID) -> Optional[Usuario]:
        query = (
            update(Usuario)
            .where(Usuario.id == usuario_id)
            .values(rol_id=rol_id)
        )
        await self.db.execute(query)
        return await self.buscarPorId(usuario_id)

    async def actualizarEstado(self, usuario_id: uuid.UUID, estado: str) -> Optional[Usuario]:
        query = (
            update(Usuario)
            .where(Usuario.id == usuario_id)
            .values(estado=estado)
        )
        await self.db.execute(query)
        return await self.buscarPorId(usuario_id)
