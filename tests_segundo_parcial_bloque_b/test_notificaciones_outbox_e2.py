"""Pruebas del sistema de Notificaciones, Dispositivos y Outbox (E2 Avisos Push).

Verifica:
- Registro y revocación de dispositivos móviles y PWA.
- Emisión de notificaciones y evento outbox en la misma transacción sin revertir si el envío push falla.
- Consulta de bandeja de notificaciones propia del usuario y marcado de lectura.
"""
from __future__ import annotations

import uuid
import pytest
from sqlalchemy import select

from backend.app.core.modules.identidad_empresas.models_notificaciones import (
    DispositivoAutorizado,
    EventoOutbox,
    Notificacion,
)
from backend.app.core.modules.identidad_empresas.services.notificacion_service import (
    NotificacionService,
    RegistroDispositivoDTO,
)


@pytest.mark.asyncio
async def test_notificaciones_registro_y_revocacion_dispositivo(http, escenario, fabrica_sesiones):
    """Verifica registro de token de dispositivo PWA y Flutter, y su revocación."""
    http.usar(escenario.usuario_a)

    disp_id = uuid.uuid4()
    # 1. Registrar dispositivo
    resp = await http.cliente.post(
        "/api/v1/notificaciones/dispositivos",
        json={
            "dispositivo_id": str(disp_id),
            "canal": "FLUTTER",
            "push_token": "fcm_test_token_123456",
            "sucursal_id": str(escenario.sucursal_a_id),
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["dispositivo_id"] == str(disp_id)
    assert data["canal"] == "FLUTTER"
    assert data["estado"] == "ACTIVO"

    # Verificar en base de datos
    async with fabrica_sesiones() as db:
        stmt = select(DispositivoAutorizado).where(
            DispositivoAutorizado.empresa_id == escenario.empresa_a_id,
            DispositivoAutorizado.dispositivo_id == disp_id,
        )
        disp_bd = (await db.execute(stmt)).scalars().first()
        assert disp_bd is not None
        assert disp_bd.estado == "ACTIVO"
        assert disp_bd.push_destino_hash is not None

    # 2. Revocar dispositivo
    resp_del = await http.cliente.delete(f"/api/v1/notificaciones/dispositivos/{disp_id}")
    assert resp_del.status_code == 204, resp_del.text

    async with fabrica_sesiones() as db:
        disp_bd2 = (await db.execute(stmt)).scalars().first()
        assert disp_bd2.estado == "REVOCADO"
        assert disp_bd2.revocado_en is not None


@pytest.mark.asyncio
async def test_notificaciones_emision_outbox_y_bandeja_lectura(http, escenario, fabrica_sesiones):
    """Verifica emisión de evento outbox, persistencia en bandeja y marcado de lectura."""
    http.usar(escenario.usuario_a)

    # 1. Emitir notificación y outbox mediante servicio
    rec_id = uuid.uuid4()
    async with fabrica_sesiones() as db:
        srv = NotificacionService(db)
        notif = await srv.emitir_notificacion(
            empresa_id=escenario.empresa_a_id,
            usuario_id=escenario.usuario_a.id,
            tipo="COMPRA_CONFIRMADA",
            titulo="¡Compra confirmada!",
            cuerpo="Tu pedido ha sido procesado y el stock está comprometido.",
            recurso_tipo="PEDIDO",
            recurso_id=rec_id,
            payload={"pedido_id": str(rec_id), "total_bob": "100.00"},
        )
        notif_id = notif.id
        await db.commit()

    # Verificar evento outbox
    async with fabrica_sesiones() as db:
        stmt_out = select(EventoOutbox).where(EventoOutbox.recurso_id == rec_id)
        ev = (await db.execute(stmt_out)).scalars().first()
        assert ev is not None
        assert ev.transicion == "COMPRA_CONFIRMADA"
        assert ev.estado == "PENDIENTE"

    # 2. Consultar bandeja vía API
    resp = await http.cliente.get("/api/v1/notificaciones/bandeja")
    assert resp.status_code == 200, resp.text
    bandeja = resp.json()
    assert len(bandeja) >= 1
    item = next(b for b in bandeja if b["id"] == str(notif_id))
    assert item["titulo"] == "¡Compra confirmada!"
    assert item["tipo"] == "COMPRA_CONFIRMADA"
    assert item["leida_en"] is None

    # 3. Marcar como leída
    resp_leer = await http.cliente.patch(f"/api/v1/notificaciones/bandeja/{notif_id}/leer")
    assert resp_leer.status_code == 200, resp_leer.text
    assert resp_leer.json()["leida_en"] is not None
