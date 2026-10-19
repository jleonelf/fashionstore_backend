"""Router IA Analítica — CU21 (reporte generativo) y CU25 (decisiones de inventario)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.dependencias import get_usuario_actual
from backend.app.core.errores import E401, E403, E404, E422
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.analitica.schemas import (
    DecisionPedirDTO,
    DecisionRespuestaDTO,
    ReportePedirDTO,
    ReporteRespuestaDTO,
)
from backend.app.core.modules.analitica.services.ia_analitica_service import IAAnaliticaService

router = APIRouter()


@router.post(
    "/reportes",
    response_model=ReporteRespuestaDTO,
    summary="Reporte generativo por voz/texto (CU21)",
    description="Solo ADMINISTRADOR/ENCARGADO. Catálogo cerrado de funciones de lectura "
    "(ventasPorSucursal, ventasPorTemporada, stockCritico, topVendidos, efectividadReservas, "
    "rotacionPorTemporada). Nunca SQL generado ni aportado; nunca muta negocio. "
    "Respuesta: función usada, parámetros validados, datos y narrativa.",
    responses={401: E401, 403: E403, 422: E422, 404: E404},
)
async def solicitarReporte(
    datos: ReportePedirDTO,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
) -> ReporteRespuestaDTO:
    return await IAAnaliticaService(db).generarReporte(usuario, datos.consulta)


@router.post(
    "/decisiones-inventario",
    response_model=DecisionRespuestaDTO,
    summary="Asistente IA de decisiones de inventario (CU25)",
    description="Solo ADMINISTRADOR/ENCARGADO. Detecta baja rotación (sugiere promoción, liquidación "
    "o traslado) y estima reposición (promedio de ventas × 14 días de proveedor). "
    "Solo recomienda: no crea promociones, traslados, recepciones ni movimientos.",
    responses={401: E401, 403: E403, 422: E422},
)
async def sugerirDecisiones(
    datos: DecisionPedirDTO,
    db: AsyncSession = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_actual),
) -> DecisionRespuestaDTO:
    return await IAAnaliticaService(db).decisionesInventario(
        usuario, dias_ventana=datos.dias_ventana, umbral_rotacion=datos.umbral_rotacion
    )
