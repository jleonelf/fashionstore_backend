import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.modules.catalogo.models import Proveedor

class ProveedorRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def buscarPorId(self, proveedor_id: uuid.UUID) -> Optional[Proveedor]:
        query = select(Proveedor).where(Proveedor.id == proveedor_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def buscarPorNit(self, nit: str) -> Optional[Proveedor]:
        query = select(Proveedor).where(Proveedor.nit == nit.strip())
        result = await self.db.execute(query)
        return result.scalars().first()

    async def listar(self, solo_activos: bool = False) -> List[Proveedor]:
        query = select(Proveedor)
        if solo_activos:
            query = query.where(Proveedor.activo == True)
        query = query.order_by(Proveedor.razon_social)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def crear(self, proveedor: Proveedor) -> Proveedor:
        self.db.add(proveedor)
        await self.db.flush()
        return proveedor
