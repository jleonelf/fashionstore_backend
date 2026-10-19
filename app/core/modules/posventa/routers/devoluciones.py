"""Router Devoluciones y mermas — CU12 (RF22)."""
from typing import Optional
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.core.dependencias import get_usuario_actual
from backend.app.core.idempotencia import validar_clave_idempotencia
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.posventa.schemas import (
    DevolucionCrearDTO,
    DevolucionDTO,
    MermaCrearDTO,
    MermaDTO,
)
from backend.app.core.modules.posventa.services.devolucion_service import DevolucionService, MermaService

router_devoluciones = APIRouter()
router_mermas = APIRouter()


@router_devoluciones.post(
    "",
    response_model=DevolucionDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar devolucion parcial (CU12)",
    description="Encargado o Administrador de la sucursal. Acumulable sin superar lo vendido (-> 409 el exceso). Reingresa disponible al costo congelado de la venta; sin reembolso monetario. Exactamente un Kardex DEVOLUCION. Requiere header Idempotency-Key.",
)
async def registrarDevolucion(
    datos: DevolucionCrearDTO,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
    clave_idempotencia: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> DevolucionDTO:
    clave = validar_clave_idempotencia(clave_idempotencia)
    servicio = DevolucionService(db)
    devolucion, _ = await servicio.registrar(usuario, datos, clave)
    return devolucion


@router_mermas.post(
    "",
    response_model=MermaDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar merma (CU12)",
    description="Encargado o Administrador de la sucursal. Exige causa (-> 400 si falta) y responsable (por defecto quien registra). Reduce disponible sin reingreso; exactamente un Kardex MERMA. Requiere header Idempotency-Key.",
)
async def registrarMerma(
    datos: MermaCrearDTO,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
    clave_idempotencia: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> MermaDTO:
    clave = validar_clave_idempotencia(clave_idempotencia)
    servicio = MermaService(db)
    merma, _ = await servicio.registrar(usuario, datos, clave)
    return merma
