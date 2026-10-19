"""Router Pagos Stripe — CU15 (RF19, RN-05)."""
import json
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Header, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.core.dependencias import get_usuario_actual
from backend.app.core.idempotencia import validar_clave_idempotencia
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.ventas_pagos.schemas import EstadoPagoDTO, IntencionCrearDTO, IntencionDTO
from backend.app.core.modules.ventas_pagos.services.stripe_service import StripeService
from backend.app.core.errores import (
    E400, E401, E403, E404, E409_IDEM, E409_NEGOCIO, E502, E503_STRIPE,
)

router = APIRouter()


@router.post(
    "/stripe/intenciones", response_model=IntencionDTO, status_code=status.HTTP_201_CREATED,
    summary="Crear o reutilizar PaymentIntent (CU15)",
    description="Cliente propietario o Administrador. Una intención por venta: FAILED reutiliza el "
    "PaymentIntent vigente; CANCELED crea uno nuevo (un PI cancelado no procesa pagos). Sin claves "
    "responde 503 STRIPE_DESHABILITADO; con clave live o fuera de Test Mode responde 503 "
    "STRIPE_MODO_NO_PERMITIDO (sin exponer la clave). Requiere header Idempotency-Key.",
    responses={400: E400, 401: E401, 403: E403, 404: E404, 409: E409_NEGOCIO, 502: E502, 503: E503_STRIPE},
)
async def crearIntencion(
    datos: IntencionCrearDTO,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
    clave_idempotencia: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> IntencionDTO:
    clave = validar_clave_idempotencia(clave_idempotencia)
    dto, _ = await StripeService(db).crearIntencion(usuario, datos.venta_id, clave)
    return dto


@router.post(
    "/stripe/intenciones/reintento", response_model=IntencionDTO, status_code=status.HTTP_200_OK,
    summary="Reintentar pago dentro de la ventana (CU15)",
    description="Reutiliza la intención vigente (FAILED) o crea una nueva (CANCELED) mientras la venta "
    "siga PENDIENTE_PAGO y no expire. Actualiza el registro Pago a la intención vigente; un webhook "
    "tardío de la intención reemplazada se ignora sin efectos. Vencida -> 409.",
    responses={400: E400, 401: E401, 403: E403, 404: E404, 409: E409_NEGOCIO, 502: E502, 503: E503_STRIPE},
)
async def reintentarIntencion(
    datos: IntencionCrearDTO,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
    clave_idempotencia: Optional[str] = Header(None, alias="Idempotency-Key"),
) -> IntencionDTO:
    clave = validar_clave_idempotencia(clave_idempotencia)
    dto, _ = await StripeService(db).crearIntencion(usuario, datos.venta_id, clave)
    return dto


@router.get(
    "/stripe/estado/{venta_id}", response_model=EstadoPagoDTO,
    summary="Consultar estado de pago para polling (CU15)",
    description="El frontend consulta; nunca confirma pagos directamente.",
    responses={401: E401, 403: E403, 404: E404},
)
async def estadoPago(
    venta_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
) -> EstadoPagoDTO:
    return await StripeService(db).estado(usuario, venta_id)


@router.post(
    "/stripe/webhook", status_code=status.HTTP_200_OK,
    summary="Webhook firmado de Stripe (CU15)",
    description="Única confirmación definitiva. Verifica la firma con el cuerpo HTTP crudo; "
    "firma inválida -> 400. Rechaza eventos con livemode=true (400) sin modificar pago, venta, "
    "pedido, inventario o Kardex. Eventos duplicados y fuera de orden son idempotentes; solo el "
    "webhook firmado de la intención vigente confirma la venta.",
    response_model=dict,
    responses={400: E400, 401: E401, 404: E404},
)
async def webhookStripe(
    request: Request,
    db: AsyncSession = Depends(get_db),
    firma: Optional[str] = Header(None, alias="Stripe-Signature"),
):
    cuerpo = await request.body()
    try:
        evento = json.loads(cuerpo.decode("utf-8") or "{}")
    except Exception:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cuerpo del webhook inválido")
    return await StripeService(db).confirmarWebhook(cuerpo, firma, evento)


@router.post(
    "/stripe/expiracion/ejecutar", status_code=status.HTTP_200_OK,
    summary="Ejecutar expiración de ventas vencidas (CU15)",
    description="Solo ADMINISTRADOR (job manual en pruebas). Advisory lock + SKIP LOCKED; "
    "cancela y libera el compromiso exactamente una vez.",
    response_model=dict,
    responses={401: E401, 403: E403},
)
async def ejecutarExpiracion(
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
):
    from backend.app.core.permisos import es_admin
    from fastapi import HTTPException

    if not es_admin(usuario):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el Administrador")
    return await StripeService(db).cancelarVencidas()
