from typing import List
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.core.dependencias import require_roles, get_usuario_actual
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.inventario.schemas import ProveedorCrearDTO, ProveedorDTO
from backend.app.core.modules.inventario.services.proveedor_service import ProveedorService

router = APIRouter()

@router.post(
    "",
    response_model=ProveedorDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar proveedor (CU04 / RF06)",
    description="Presentación gestionarProveedores() -> Controller ProveedorService.crear() -> Datos ProveedorRepository.crear()"
)
async def gestionarProveedores(
    datos: ProveedorCrearDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> ProveedorDTO:
    servicio = ProveedorService(db)
    return await servicio.crear(datos)

@router.get(
    "",
    response_model=List[ProveedorDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar proveedores (CU04)",
)
async def listarProveedores(
    solo_activos: bool = Query(False, description="Filtrar solo activos"),
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_usuario_actual)
) -> List[ProveedorDTO]:
    servicio = ProveedorService(db)
    return await servicio.listar(solo_activos=solo_activos)
