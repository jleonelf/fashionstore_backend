"""Tareas programadas Ciclo 2 — job de expiracion CU24.

La logica vive en ReservaService.expirarVencidas() (testeable con reloj
inyectado, advisory lock PostgreSQL y SKIP LOCKED). Este modulo solo
programa su ejecucion periodica con APScheduler cuando el ajuste
EXPIRACION_JOB_ACTIVO esta activo (produccion). En pruebas permanece
apagado y se usa el endpoint manual.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)
_scheduler = None


async def ejecutar_expiracion_programada() -> None:
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.core.modules.reservas_traslados.services.reserva_service import ReservaService
    from backend.app.core.modules.ventas_pagos.services.stripe_service import StripeService

    async with AsyncSessionLocal() as db:
        servicio = ReservaService(db)
        try:
            resultado = await servicio.expirarVencidas()
            logger.info(
                "Expiracion CU24: procesadas=%s expiradas=%s omitidas=%s errores=%s bloqueo=%s",
                resultado.procesadas, len(resultado.expiradas),
                len(resultado.omitidas), len(resultado.errores), resultado.bloqueo_activo,
            )
        except Exception:
            logger.exception("Fallo el job de expiracion CU24")
    # Ciclo 3 (CU15): ventas digitales PENDIENTE_PAGO vencidas (mismo scheduler).
    async with AsyncSessionLocal() as db:
        try:
            resumen = await StripeService(db).cancelarVencidas()
            logger.info(
                "Expiracion CU15: procesadas=%s canceladas=%s",
                resumen.get("procesadas"), len(resumen.get("canceladas", [])),
            )
        except Exception:
            logger.exception("Fallo el job de expiracion CU15")


def iniciar_scheduler(intervalo_minutos: int = 10):
    """Inicia APScheduler con una sola instancia (max_instances=1, coalesce)."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
    except ImportError:  # pragma: no cover (apscheduler en requirements)
        logger.warning("APScheduler no instalado: job CU24 solo manual")
        return None
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        ejecutar_expiracion_programada,
        "interval",
        minutes=intervalo_minutos,
        id="cu24_expirar_vencidas",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("Scheduler CU24 iniciado cada %s min", intervalo_minutos)
    return _scheduler


def detener_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
