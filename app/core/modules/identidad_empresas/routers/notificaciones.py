"""Router de Notificaciones, Dispositivos y Bandeja (E2 Avisos Push)."""
from __future__ import annotations

import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.dependencias import get_usuario_actual
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.identidad_empresas.services.notificacion_service import (
    DispositivoDTO,
    NotificacionDTO,
    NotificacionService,
    RegistroDispositivoDTO,
)

router = APIRouter()


@router.post(
    "/dispositivos",
    response_model=DispositivoDTO,
    status_code=status.HTTP_200_OK,
    summary="Registrar o actualizar token de dispositivo (PWA o Flutter)",
)
async def registrar_dispositivo(
    dto: RegistroDispositivoDTO,
    usuario: Usuario = Depends(get_usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    srv = NotificacionService(db)
    res = await srv.registrar_dispositivo(usuario, dto)
    await db.commit()
    return res


@router.delete(
    "/dispositivos/{dispositivo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revocar registro de dispositivo",
)
async def revocar_dispositivo(
    dispositivo_id: uuid.UUID,
    usuario: Usuario = Depends(get_usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    srv = NotificacionService(db)
    await srv.revocar_dispositivo(usuario, dispositivo_id)
    await db.commit()
    return None


@router.get(
    "/bandeja",
    response_model=List[NotificacionDTO],
    summary="Consultar bandeja de notificaciones propia",
)
async def consultar_bandeja(
    limite: int = 50,
    usuario: Usuario = Depends(get_usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    srv = NotificacionService(db)
    return await srv.listar_bandeja(usuario, limite=limite)


@router.patch(
    "/bandeja/{notificacion_id}/leer",
    response_model=NotificacionDTO,
    summary="Marcar notificación como leída",
)
async def marcar_notificacion_leida(
    notificacion_id: uuid.UUID,
    usuario: Usuario = Depends(get_usuario_actual),
    db: AsyncSession = Depends(get_db),
):
    srv = NotificacionService(db)
    res = await srv.marcar_leida(usuario, notificacion_id)
    await db.commit()
    return res
