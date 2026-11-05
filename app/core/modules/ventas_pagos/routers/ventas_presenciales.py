"""Router Ventas Presenciales en Caja — CU19.

Ruta:
- POST /ventas/presenciales/liquidar
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.dependencias import get_usuario_actual
from backend.app.core.idempotencia import validar_clave_idempotencia
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.ventas_pagos.services.venta_presencial_service import (
    VentaLiquidadaDTO,
    VentaPresencialLiquidarDTO,
    VentaPresencialService,
)

router = APIRouter()


@router.post(
    "/liquidar",
    response_model=VentaLiquidadaDTO,
    status_code=status.HTTP_201_CREATED,
    summary="Liquidar venta presencial en caja (CU19)",
    description=(
        "Cajero o Administrador. Valida stock libre y lo bloquea atómicamente por sucursal. "
        "Liquida pago en EFECTIVO, SALDO o STRIPE_TEST, registra cambio entregado, emite "
        "Kardex VENTA_PRESENCIAL único por ítem y genera el comprobante operativo. "
        "Requiere header Idempotency-Key."
    ),
)
async def liquidar_venta_presencial(
    datos: VentaPresencialLiquidarDTO,
    clave_idempotencia: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
) -> VentaLiquidadaDTO:
    clave = validar_clave_idempotencia(clave_idempotencia)
    servicio = VentaPresencialService(db)
    return await servicio.liquidar(usuario, datos, clave)
