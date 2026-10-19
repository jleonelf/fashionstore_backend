import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.core.modules.catalogo.services.catalogo_service import CatalogoService
from backend.app.core.modules.inventario.services.inventario_service import InventarioService
from backend.app.core.modules.catalogo.schemas import ProductoDTO
from backend.app.core.modules.inventario.schemas import DisponibilidadSucursalDTO, FiltrosOpcionesDTO
from sqlalchemy import select
from backend.app.core.database import AsyncSessionLocal

router = APIRouter()

@router.get(
    "/filtros-opciones",
    response_model=FiltrosOpcionesDTO,
    status_code=status.HTTP_200_OK,
    summary="Opciones de filtros para catálogo (CU06)",
    description="Retorna listas de categorías, tallas, colores, temporadas, colecciones, géneros y marcas para construir filtros en tiempo real. Solo lectura."
)
async def filtrosOpciones(db: AsyncSession = Depends(get_db)) -> FiltrosOpcionesDTO:
    from backend.app.core.modules.catalogo.repositories.maestro_repository import MaestroRepository
    from backend.app.core.modules.catalogo.repositories.producto_repository import ProductoRepository
    from sqlalchemy import distinct, select
    from backend.app.core.modules.catalogo.models import Producto

    maestro_repo = MaestroRepository(db)
    categorias = await maestro_repo.listarCategorias(solo_activas=True)
    tallas = await maestro_repo.listarTallas(solo_activas=True)
    colores = await maestro_repo.listarColores(solo_activos=True)
    temporadas = await maestro_repo.listarTemporadas(solo_activas=True)
    colecciones = await maestro_repo.listarColecciones(solo_activas=True)

    q_genero = select(distinct(Producto.genero)).where(Producto.activo == True, Producto.genero.is_not(None))
    result_g = await db.execute(q_genero)
    generos = [row[0] for row in result_g.all() if row[0]]

    q_marca = select(distinct(Producto.marca)).where(Producto.activo == True, Producto.marca.is_not(None))
    result_m = await db.execute(q_marca)
    marcas = [row[0] for row in result_m.all() if row[0]]

    return {
        "categorias": [{"id": str(c.id), "nombre": c.nombre} for c in categorias],
        "tallas": [{"id": str(t.id), "nombre": t.nombre, "orden": t.orden} for t in tallas],
        "colores": [{"id": str(c.id), "nombre": c.nombre, "codigo_hex": c.codigo_hex} for c in colores],
        "temporadas": [{"id": str(t.id), "nombre": t.nombre} for t in temporadas],
        "colecciones": [{"id": str(c.id), "nombre": c.nombre} for c in colecciones],
        "generos": generos,
        "marcas": marcas,
    }

@router.get(
    "/productos",
    response_model=List[ProductoDTO],
    status_code=status.HTTP_200_OK,
    summary="Consultar catálogo (alias CU06)",
    description="Alias de GET /api/v1/productos para Presentación consultarCatalogo(). Delega a CatalogoService.listar()/filtrar()."
)
async def consultarCatalogoAlias(
    solo_activos: bool = Query(True),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    categoria_id: Optional[uuid.UUID] = Query(None),
    talla_id: Optional[uuid.UUID] = Query(None),
    color_id: Optional[uuid.UUID] = Query(None),
    temporada_id: Optional[uuid.UUID] = Query(None),
    coleccion_id: Optional[uuid.UUID] = Query(None),
    marca: Optional[str] = Query(None),
    genero: Optional[str] = Query(None),
    texto: Optional[str] = Query(None),
    busqueda: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    precio_min: Optional[float] = Query(None, ge=0),
    precio_max: Optional[float] = Query(None, ge=0),
    codigo_hex: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
) -> List[ProductoDTO]:
    servicio = CatalogoService(db)
    texto_final = texto or busqueda or q
    tiene_filtro = any([categoria_id, talla_id, color_id, temporada_id, coleccion_id, marca, genero, texto_final, precio_min is not None, precio_max is not None, codigo_hex])
    if tiene_filtro:
        return await servicio.filtrar(
            texto=texto_final,
            categoria_id=categoria_id,
            talla_id=talla_id,
            color_id=color_id,
            temporada_id=temporada_id,
            coleccion_id=coleccion_id,
            marca=marca,
            genero=genero,
            precio_min=precio_min,
            precio_max=precio_max,
            codigo_hex=codigo_hex,
            solo_activos=solo_activos,
            limit=limit,
            offset=offset
        )
    return await servicio.listar(solo_activos=solo_activos, limit=limit, offset=offset)

@router.get(
    "/variantes/{variante_id}/disponibilidad",
    response_model=List[DisponibilidadSucursalDTO],
    status_code=status.HTTP_200_OK,
    summary="Disponibilidad por sucursal (alias CU06)",
    description="Alias de GET /api/v1/variantes/{id}/disponibilidad para consultarDisponibilidad()"
)
async def consultarDisponibilidadAlias(
    variante_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> List[DisponibilidadSucursalDTO]:
    servicio = InventarioService(db)
    return await servicio.disponibilidadPorSucursal(variante_id)
