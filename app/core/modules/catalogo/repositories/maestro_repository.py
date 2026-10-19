import uuid
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.modules.catalogo.models import Talla, Color, Categoria, Temporada, Coleccion


class MaestroRepository:
    """
    Datos MaestroRepository.* para CU05
    Maneja Tallas, Colores, Categorias, Temporadas, Colecciones
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- Talla ----------
    async def buscarTallaPorId(self, talla_id: uuid.UUID) -> Optional[Talla]:
        result = await self.db.execute(select(Talla).where(Talla.id == talla_id))
        return result.scalars().first()

    async def buscarTallaPorNombre(self, nombre: str) -> Optional[Talla]:
        result = await self.db.execute(select(Talla).where(Talla.nombre.ilike(nombre.strip())))
        return result.scalars().first()

    async def listarTallas(self, solo_activas: bool = False) -> List[Talla]:
        q = select(Talla)
        if solo_activas:
            q = q.where(Talla.activo == True)
        q = q.order_by(Talla.orden, Talla.nombre)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def crearTalla(self, talla: Talla) -> Talla:
        self.db.add(talla)
        await self.db.flush()
        return talla

    async def actualizarTalla(self, talla: Talla) -> Talla:
        await self.db.flush()
        return talla

    # ---------- Color ----------
    async def buscarColorPorId(self, color_id: uuid.UUID) -> Optional[Color]:
        result = await self.db.execute(select(Color).where(Color.id == color_id))
        return result.scalars().first()

    async def buscarColorPorNombre(self, nombre: str) -> Optional[Color]:
        result = await self.db.execute(select(Color).where(Color.nombre.ilike(nombre.strip())))
        return result.scalars().first()

    async def listarColores(self, solo_activos: bool = False) -> List[Color]:
        q = select(Color)
        if solo_activos:
            q = q.where(Color.activo == True)
        q = q.order_by(Color.nombre)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def crearColor(self, color: Color) -> Color:
        self.db.add(color)
        await self.db.flush()
        return color

    async def actualizarColor(self, color: Color) -> Color:
        await self.db.flush()
        return color

    # ---------- Categoria ----------
    async def buscarCategoriaPorId(self, categoria_id: uuid.UUID) -> Optional[Categoria]:
        result = await self.db.execute(select(Categoria).where(Categoria.id == categoria_id))
        return result.scalars().first()

    async def buscarCategoriaPorNombreYPadre(self, nombre: str, categoria_padre_id: Optional[uuid.UUID]) -> Optional[Categoria]:
        if categoria_padre_id is None:
            q = select(Categoria).where(Categoria.categoria_padre_id.is_(None), Categoria.nombre.ilike(nombre.strip()))
        else:
            q = select(Categoria).where(Categoria.categoria_padre_id == categoria_padre_id, Categoria.nombre.ilike(nombre.strip()))
        result = await self.db.execute(q)
        return result.scalars().first()

    async def listarCategorias(self, solo_activas: bool = False) -> List[Categoria]:
        q = select(Categoria)
        if solo_activas:
            q = q.where(Categoria.activo == True)
        q = q.order_by(Categoria.nombre)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def crearCategoria(self, categoria: Categoria) -> Categoria:
        self.db.add(categoria)
        await self.db.flush()
        return categoria

    async def actualizarCategoria(self, categoria: Categoria) -> Categoria:
        await self.db.flush()
        return categoria

    # ---------- Temporada ----------
    async def buscarTemporadaPorId(self, temporada_id: uuid.UUID) -> Optional[Temporada]:
        result = await self.db.execute(select(Temporada).where(Temporada.id == temporada_id))
        return result.scalars().first()

    async def buscarTemporadaPorNombre(self, nombre: str) -> Optional[Temporada]:
        result = await self.db.execute(select(Temporada).where(Temporada.nombre.ilike(nombre.strip())))
        return result.scalars().first()

    async def listarTemporadas(self, solo_activas: bool = False) -> List[Temporada]:
        q = select(Temporada)
        if solo_activas:
            q = q.where(Temporada.activa == True)
        q = q.order_by(Temporada.nombre)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def crearTemporada(self, temporada: Temporada) -> Temporada:
        self.db.add(temporada)
        await self.db.flush()
        return temporada

    async def actualizarTemporada(self, temporada: Temporada) -> Temporada:
        await self.db.flush()
        return temporada

    # ---------- Coleccion ----------
    async def buscarColeccionPorId(self, coleccion_id: uuid.UUID) -> Optional[Coleccion]:
        result = await self.db.execute(select(Coleccion).where(Coleccion.id == coleccion_id))
        return result.scalars().first()

    async def buscarColeccionPorNombre(self, nombre: str) -> Optional[Coleccion]:
        result = await self.db.execute(select(Coleccion).where(Coleccion.nombre.ilike(nombre.strip())))
        return result.scalars().first()

    async def listarColecciones(self, solo_activas: bool = False) -> List[Coleccion]:
        q = select(Coleccion)
        if solo_activas:
            q = q.where(Coleccion.activa == True)
        q = q.order_by(Coleccion.nombre)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def crearColeccion(self, coleccion: Coleccion) -> Coleccion:
        self.db.add(coleccion)
        await self.db.flush()
        return coleccion

    async def actualizarColeccion(self, coleccion: Coleccion) -> Coleccion:
        await self.db.flush()
        return coleccion
