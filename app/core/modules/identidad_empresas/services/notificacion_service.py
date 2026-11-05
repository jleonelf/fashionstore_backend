"""Servicio de Notificaciones, Bandeja y Dispositivos Autorizados (E2).

Implementa:
- Registro y revocación de dispositivos móviles y PWA (seguridad.dispositivos_autorizados).
- Emisión transaccional de eventos de negocio en outbox (comercial.eventos_outbox).
- Bandeja de notificaciones del cliente/usuario (comercial.notificaciones).
- Marcado de lectura y consulta durable.
- Caída de push o simulación sin revertir transacciones de negocio.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.identidad_empresas.models_notificaciones import (
    DispositivoAutorizado,
    EventoOutbox,
    Notificacion,
)


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


class RegistroDispositivoDTO(BaseModel):
    dispositivo_id: uuid.UUID
    canal: Literal["PWA", "FLUTTER"]
    push_token: Optional[str] = None
    sucursal_id: Optional[uuid.UUID] = None


class DispositivoDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dispositivo_id: uuid.UUID
    canal: str
    estado: str
    creado_en: datetime


class NotificacionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tipo: str
    titulo: str
    cuerpo: str
    recurso_tipo: Optional[str] = None
    recurso_id: Optional[uuid.UUID] = None
    creada_en: datetime
    leida_en: Optional[datetime] = None


class NotificacionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def registrar_dispositivo(
        self, usuario: Usuario, dto: RegistroDispositivoDTO
    ) -> DispositivoDTO:
        if not usuario.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario sin empresa asignada",
            )

        token_bytes = dto.push_token.encode("utf-8") if dto.push_token else None
        token_hash = hashlib.sha256(token_bytes).hexdigest() if token_bytes else None

        stmt = select(DispositivoAutorizado).where(
            DispositivoAutorizado.empresa_id == usuario.empresa_id,
            DispositivoAutorizado.usuario_id == usuario.id,
            DispositivoAutorizado.canal == dto.canal,
            DispositivoAutorizado.dispositivo_id == dto.dispositivo_id,
        )
        disp = (await self.db.execute(stmt)).scalars().first()

        ahora = _ahora_utc()
        if disp is not None:
            disp.estado = "ACTIVO"
            disp.push_destino_cifrado = token_bytes
            disp.push_destino_hash = token_hash
            disp.sucursal_id = dto.sucursal_id
            disp.revision += 1
            disp.revocado_en = None
        else:
            disp = DispositivoAutorizado(
                id=uuid.uuid4(),
                empresa_id=usuario.empresa_id,
                usuario_id=usuario.id,
                sucursal_id=dto.sucursal_id,
                canal=dto.canal,
                dispositivo_id=dto.dispositivo_id,
                push_destino_cifrado=token_bytes,
                push_destino_hash=token_hash,
                estado="ACTIVO",
                revision=1,
                creado_en=ahora,
            )
            self.db.add(disp)

        await self.db.flush()
        return DispositivoDTO.model_validate(disp)

    async def revocar_dispositivo(
        self, usuario: Usuario, dispositivo_id: uuid.UUID
    ) -> None:
        if not usuario.empresa_id:
            return

        stmt = select(DispositivoAutorizado).where(
            DispositivoAutorizado.empresa_id == usuario.empresa_id,
            DispositivoAutorizado.usuario_id == usuario.id,
            DispositivoAutorizado.dispositivo_id == dispositivo_id,
            DispositivoAutorizado.estado == "ACTIVO",
        )
        disp = (await self.db.execute(stmt)).scalars().first()
        if disp is not None:
            disp.estado = "REVOCADO"
            disp.revocado_en = _ahora_utc()
            disp.revision += 1
            await self.db.flush()

    async def emitir_notificacion(
        self,
        empresa_id: uuid.UUID,
        usuario_id: uuid.UUID,
        tipo: str,
        titulo: str,
        cuerpo: str,
        recurso_tipo: Optional[str] = None,
        recurso_id: Optional[uuid.UUID] = None,
        payload: Optional[Dict[str, Any]] = None,
        dispositivo_id: Optional[uuid.UUID] = None,
    ) -> Notificacion:
        ahora = _ahora_utc()
        outbox_id = uuid.uuid4()
        evento = EventoOutbox(
            id=outbox_id,
            empresa_id=empresa_id,
            recurso_tipo=recurso_tipo or "NOTIFICACION",
            recurso_id=recurso_id or outbox_id,
            transicion=tipo,
            revision=1,
            dispositivo_id=dispositivo_id,
            payload=payload or {"titulo": titulo, "cuerpo": cuerpo},
            estado="PENDIENTE",
            intentos=0,
            creado_en=ahora,
        )
        self.db.add(evento)

        notif = Notificacion(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            usuario_id=usuario_id,
            outbox_id=outbox_id,
            tipo=tipo,
            titulo=titulo,
            cuerpo=cuerpo,
            recurso_tipo=recurso_tipo,
            recurso_id=recurso_id,
            creada_en=ahora,
        )
        self.db.add(notif)
        await self.db.flush()
        return notif

    async def listar_bandeja(
        self, usuario: Usuario, limite: int = 50
    ) -> List[NotificacionDTO]:
        if not usuario.empresa_id:
            return []

        stmt = (
            select(Notificacion)
            .where(
                Notificacion.empresa_id == usuario.empresa_id,
                Notificacion.usuario_id == usuario.id,
            )
            .order_by(desc(Notificacion.creada_en))
            .limit(limite)
        )
        filas = (await self.db.execute(stmt)).scalars().all()
        return [NotificacionDTO.model_validate(f) for f in filas]

    async def marcar_leida(
        self, usuario: Usuario, notificacion_id: uuid.UUID
    ) -> NotificacionDTO:
        if not usuario.empresa_id:
            raise HTTPException(status_code=400, detail="Sin empresa asignada")

        stmt = select(Notificacion).where(
            Notificacion.id == notificacion_id,
            Notificacion.empresa_id == usuario.empresa_id,
            Notificacion.usuario_id == usuario.id,
        )
        notif = (await self.db.execute(stmt)).scalars().first()
        if notif is None:
            raise HTTPException(status_code=404, detail="Notificación no encontrada")

        if notif.leida_en is None:
            notif.leida_en = _ahora_utc()
            await self.db.flush()

        return NotificacionDTO.model_validate(notif)
