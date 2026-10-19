import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.core.dependencias import require_roles, get_usuario_actual
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.organizacion.schemas import (
    SucursalCrearDTO,
    SucursalDTO,
    ConfigurarTarifasDeliveryDTO,
    ConfigurarAdelantoDTO,
)
from backend.app.core.modules.organizacion.services.sucursal_service import SucursalService

router = APIRouter()


@router.post(
    "",
    response_model=SucursalDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar nueva sucursal (CU03 / RF03)",
    description="Permite al Administrador registrar una sucursal con su ubicación, anillo y parámetros de delivery."
)
async def registrarSucursal(
    datos_sucursal: SucursalCrearDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> SucursalDTO:
    servicio = SucursalService(db)
    return await servicio.crear(datos_sucursal)


@router.get(
    "",
    response_model=List[SucursalDTO],
    status_code=status.HTTP_200_OK,
    summary="Listar sucursales de la cadena (CU03 / RF03)",
    description="Retorna las sucursales con opción de filtrar por ciudad_id."
)
async def gestionarSucursales(
    ciudad_id: Optional[uuid.UUID] = Query(None, description="Filtrar sucursales por ID de ciudad"),
    solo_activas: bool = True,
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_usuario_actual)
) -> List[SucursalDTO]:
    servicio = SucursalService(db)
    return await servicio.listar(ciudad_id=ciudad_id, solo_activas=solo_activas)


@router.get(
    "/{sucursal_id}",
    response_model=SucursalDTO,
    status_code=status.HTTP_200_OK,
    summary="Obtener detalle de sucursal (CU03 / RF03)"
)
async def obtenerSucursalPorId(
    sucursal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: Usuario = Depends(get_usuario_actual)
) -> SucursalDTO:
    servicio = SucursalService(db)
    return await servicio.obtenerPorId(sucursal_id)


@router.patch(
    "/{sucursal_id}/tarifas",
    response_model=SucursalDTO,
    status_code=status.HTTP_200_OK,
    summary="Configurar tarifas y cobertura de delivery por anillos (CU03 / RF03)",
    description="Actualiza la tarifa base, incremento por anillo y rango de cobertura de delivery para la sucursal."
)
async def configurarTarifasDelivery(
    sucursal_id: uuid.UUID,
    datos_tarifas: ConfigurarTarifasDeliveryDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> SucursalDTO:
    servicio = SucursalService(db)
    return await servicio.actualizarTarifas(sucursal_id, datos_tarifas)


@router.patch(
    "/{sucursal_id}/adelanto",
    response_model=SucursalDTO,
    status_code=status.HTTP_200_OK,
    summary="Configurar política de adelanto de la sucursal (RN-03)",
    description="Activa o desactiva el adelanto (MONTO_FIJO o PORCENTAJE con valor). La reserva/pago congelan la política aplicada; el adelanto es no reembolsable y extiende la vigencia a 72 h."
)
async def configurarAdelanto(
    sucursal_id: uuid.UUID,
    datos_adelanto: ConfigurarAdelantoDTO,
    db: AsyncSession = Depends(get_db),
    _admin: Usuario = Depends(require_roles("ADMINISTRADOR"))
) -> SucursalDTO:
    servicio = SucursalService(db)
    return await servicio.actualizarAdelanto(sucursal_id, datos_adelanto)
