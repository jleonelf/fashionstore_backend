import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.core.dependencias import require_roles
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.catalogo.schemas import VarianteCrearDTO, VarianteDTO, VarianteActualizarDTO
from backend.app.core.modules.inventario.schemas import DisponibilidadSucursalDTO
from backend.app.core.modules.catalogo.services.variante_service import VarianteService
from backend.app.core.modules.inventario.services.inventario_service import InventarioService

router = APIRouter()

@router.post(
    "",
    response_model=VarianteDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Crear variante de producto (CU05 / RF05)",
    description="Presentación gestionarVariantes() -> Controller VarianteService.crear() -> Datos VarianteRepository.crear(). UQ producto+talla+color, sku único, codigo_barras único, precio >=0, activa. 409 Conflict si duplica."
)
async def gestionarVariantes(
    datos: VarianteCrearDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> VarianteDTO:
    servicio = VarianteService(db)
    return await servicio.crear(datos)

@router.get(
    "",
    response_model=List[VarianteDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar variantes (CU05)",
    description="VarianteRepository.listar() — base para CU06 disponibilidad"
)
async def listarVariantes(
    producto_id: Optional[uuid.UUID] = Query(None, description="Filtrar por producto"),
    solo_activas: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
) -> List[VarianteDTO]:
    servicio = VarianteService(db)
    return await servicio.listar(producto_id=producto_id, solo_activas=solo_activas, limit=limit, offset=offset)

@router.get(
    "/{variante_id}",
    response_model=VarianteDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener variante por ID (CU05)"
)
async def obtenerVariante(
    variante_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> VarianteDTO:
    servicio = VarianteService(db)
    return await servicio.obtenerPorId(variante_id)

@router.put(
    "/{variante_id}",
    response_model=VarianteDTO,
    status_code=status.HTTP_200_OK,
    summary="Actualizar variante (CU05)"
)
async def actualizarVariante(
    variante_id: uuid.UUID,
    datos: VarianteActualizarDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> VarianteDTO:
    servicio = VarianteService(db)
    return await servicio.actualizar(variante_id, datos)

@router.patch(
    "/{variante_id}/activacion",
    response_model=VarianteDTO,
    status_code=status.HTTP_200_OK,
    summary="Activar/desactivar variante (CU05)"
)
async def toggleVariante(
    variante_id: uuid.UUID,
    activa: bool = Query(..., description="Nuevo estado activo"),
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> VarianteDTO:
    servicio = VarianteService(db)
    return await servicio.actualizar(variante_id, VarianteActualizarDTO(activa=activa))

@router.get(
    "/{variante_id}/disponibilidad",
    response_model=List[DisponibilidadSucursalDTO],
    status_code=status.HTTP_200_OK,
    summary="Consultar disponibilidad por sucursal (CU06 / RF08)",
    description="Presentación consultarDisponibilidad() -> Controller InventarioService.disponibilidadPorSucursal() -> Datos InventarioRepository.porVariante(). Lista sucursales con disponible>0, diferenciando disponible, reservado, comprometido_traslado, en_transito. Por sucursal, no total global. Solo lectura."
)
async def consultarDisponibilidad(
    variante_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
) -> List[DisponibilidadSucursalDTO]:
    servicio = InventarioService(db)
    return await servicio.disponibilidadPorSucursal(variante_id)
