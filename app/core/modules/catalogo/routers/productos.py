import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.core.dependencias import require_roles
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.catalogo.schemas import ProductoCrearDTO, ProductoDTO, ProductoActualizarDTO
from backend.app.core.modules.catalogo.services.producto_service import ProductoService

router = APIRouter()

@router.post(
    "",
    response_model=ProductoDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear producto con imágenes y asociaciones (CU05 / RF04, RF05, RF23)",
    description="Presentación gestionarProductos() -> Controller ProductoService.crear() -> Datos ProductoRepository.crear(). Valida categoria_id, proveedor_principal_id, precio_base >=0, imagenes y temporadas/colecciones"
)
async def gestionarProductos(
    datos: ProductoCrearDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> ProductoDTO:
    servicio = ProductoService(db)
    return await servicio.crear(datos)

@router.get(
    "",
    response_model=List[ProductoDTO],
    status_code=status.HTTP_200_OK,
    summary="Consultar catálogo con filtros avanzados (CU06 / RF05, RF07, RF08)",
    description="Presentación consultarCatalogo()/filtrarCatalogo() -> Controller CatalogoService.listar()/filtrar() -> Datos ProductoRepository.buscarConFiltros(). Filtros: categoria, talla, color, temporada, coleccion, precio (rango), genero, marca, búsqueda texto. Solo activos por defecto activo=true. Paginación."
)
async def listarProductos(
    solo_activos: bool = Query(True, description="Filtrar solo activos (default true para catálogo)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    categoria_id: Optional[uuid.UUID] = Query(None, description="Filtrar por categoría"),
    talla_id: Optional[uuid.UUID] = Query(None, description="Filtrar por talla (vía variantes)"),
    color_id: Optional[uuid.UUID] = Query(None, description="Filtrar por color (vía variantes)"),
    temporada_id: Optional[uuid.UUID] = Query(None, description="Filtrar por temporada"),
    coleccion_id: Optional[uuid.UUID] = Query(None, description="Filtrar por colección"),
    marca: Optional[str] = Query(None),
    genero: Optional[str] = Query(None),
    texto: Optional[str] = Query(None, description="Búsqueda por nombre/descripción (alias busqueda)"),
    busqueda: Optional[str] = Query(None, description="Alias de texto"),
    q: Optional[str] = Query(None, description="Alias búsqueda"),
    precio_min: Optional[float] = Query(None, ge=0, description="Precio mínimo"),
    precio_max: Optional[float] = Query(None, ge=0, description="Precio máximo"),
    codigo_hex: Optional[str] = Query(None, description="Filtrar por color hex #RRGGBB"),
    activo: Optional[bool] = Query(None, description="Override activo (si se quiere incluir inactivos)"),
    db: AsyncSession = Depends(get_db)
) -> List[ProductoDTO]:
    from backend.app.core.modules.catalogo.services.catalogo_service import CatalogoService
    servicio = CatalogoService(db)
    texto_final = texto or busqueda or q
    tiene_filtro = any([categoria_id, talla_id, color_id, temporada_id, coleccion_id, marca, genero, texto_final, precio_min is not None, precio_max is not None, codigo_hex])
    if activo is not None:
        solo_activos = activo
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
    "/{producto_id}",
    response_model=ProductoDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener producto por ID (CU05)"
)
async def obtenerProducto(
    producto_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> ProductoDTO:
    servicio = ProductoService(db)
    return await servicio.obtenerPorId(producto_id)

@router.put(
    "/{producto_id}",
    response_model=ProductoDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar producto (CU05 / RF04)",
    description="Controller ProductoService.actualizar() -> Datos ProductoRepository.actualizar()"
)
async def actualizarProducto(
    producto_id: uuid.UUID,
    datos: ProductoActualizarDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> ProductoDTO:
    servicio = ProductoService(db)
    return await servicio.actualizar(producto_id, datos)

@router.patch(
    "/{producto_id}/activacion",
    response_model=ProductoDTO,
    status_code=status.HTTP_200_OK,
    summary="Activar/desactivar producto (CU05)"
)
async def toggleProducto(
    producto_id: uuid.UUID,
    activo: bool = Query(..., description="Nuevo estado activo"),
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> ProductoDTO:
    servicio = ProductoService(db)
    return await servicio.actualizar(producto_id, ProductoActualizarDTO(activo=activo))
