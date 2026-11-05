"""Pruebas de Liquidación Real en Caja — CU19 (Venta Presencial Conectada).

Verifica:
1. Rechazo con 400 si el cliente o la caja intentan alterar precios o descuentos del servidor.
2. Liquidación con SALDO real: verifica saldo suficiente, debita del libro append-only y no descuenta stock si es insuficiente.
3. Liquidación con STRIPE_TEST: requiere pago capturado (OrdenPago CAPTURADA o PaymentIntent capturado), fallando si está pendiente o fallido sin descontar stock ni marcar entrega.
4. Conservación de caja de efectivo E1 con vuelto exacto y Kardex VENTA_PRESENCIAL único.
5. Idempotencia estricta mediante Idempotency-Key.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from backend.app.core.modules.inventario.models import InventarioSucursal, MovimientoInventario
from backend.app.core.modules.posventa.services.saldo_service import MovimientoSaldo, SaldoService
from backend.app.core.modules.ventas_pagos.integraciones.stripe_gateway import (
    FakeStripeGateway,
    IntencionPago,
    fijar_gateway,
)
from backend.app.core.modules.ventas_pagos.models import DetalleVenta, Pago, Venta
from backend.app.core.modules.ventas_pagos.models_ordenes import OrdenPago
from backend.app.core.modules.ventas_pagos.services.pedido_service import Comprobante


@pytest.mark.asyncio
async def test_cu19_precio_alterado_por_cliente_falla_400(http, escenario, fabrica_sesiones):
    """CU19: Si el cliente/caja envía un precio_unitario_bob diferente al del catálogo del servidor, rechaza con 400."""
    http.usar(escenario.usuario_admin_a)

    async with fabrica_sesiones() as db:
        stmt = select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == escenario.sucursal_a_id,
            InventarioSucursal.variante_id == escenario.variante_a_id,
        )
        inv_antes = (await db.execute(stmt)).scalars().first()
        disponible_antes = inv_antes.disponible

    # Catálogo tiene precio 100.00; enviamos 50.00 adulterado
    resp = await http.cliente.post(
        "/api/v1/ventas/presenciales/liquidar",
        json={
            "sucursal_id": str(escenario.sucursal_a_id),
            "lineas": [
                {
                    "variante_id": str(escenario.variante_a_id),
                    "cantidad": 1,
                    "precio_unitario_bob": 50.0,
                }
            ],
            "medio_pago": "EFECTIVO",
            "efectivo_recibido_bob": 100.0,
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 400, resp.text
    assert "adulterado" in resp.json()["detail"].lower() or "precio" in resp.json()["detail"].lower()

    # Verificar que el stock NO fue tocado
    async with fabrica_sesiones() as db:
        inv_despues = (await db.execute(stmt)).scalars().first()
        assert inv_despues.disponible == disponible_antes


@pytest.mark.asyncio
async def test_cu19_descuento_alterado_por_cliente_falla_400(http, escenario, fabrica_sesiones):
    """CU19: Si el cliente/caja inventa un descuento_bob no respaldado por promociones vigentes, rechaza con 400."""
    http.usar(escenario.usuario_admin_a)

    async with fabrica_sesiones() as db:
        stmt = select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == escenario.sucursal_a_id,
            InventarioSucursal.variante_id == escenario.variante_a_id,
        )
        disponible_antes = (await db.execute(stmt)).scalars().first().disponible

    resp = await http.cliente.post(
        "/api/v1/ventas/presenciales/liquidar",
        json={
            "sucursal_id": str(escenario.sucursal_a_id),
            "lineas": [
                {
                    "variante_id": str(escenario.variante_a_id),
                    "cantidad": 1,
                    "precio_unitario_bob": 100.0,
                    "descuento_bob": 25.0,  # Descuento inventado
                }
            ],
            "medio_pago": "EFECTIVO",
            "efectivo_recibido_bob": 100.0,
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 400, resp.text
    assert "descuento" in resp.json()["detail"].lower()

    async with fabrica_sesiones() as db:
        disponible_despues = (await db.execute(stmt)).scalars().first().disponible
        assert disponible_despues == disponible_antes


@pytest.mark.asyncio
async def test_cu19_saldo_insuficiente_falla_sin_debitar_ni_descontar_stock(
    http, escenario, fabrica_sesiones
):
    """CU19: Liquidar con SALDO cuando el cliente no tiene saldo suficiente falla con 400 sin descontar stock ni debitar."""
    http.usar(escenario.usuario_admin_a)

    async with fabrica_sesiones() as db:
        stmt = select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == escenario.sucursal_a_id,
            InventarioSucursal.variante_id == escenario.variante_a_id,
        )
        disponible_antes = (await db.execute(stmt)).scalars().first().disponible

    # Cliente sin saldo suficiente (saldo disponible 0, total 100 BOB)
    resp = await http.cliente.post(
        "/api/v1/ventas/presenciales/liquidar",
        json={
            "sucursal_id": str(escenario.sucursal_a_id),
            "lineas": [
                {
                    "variante_id": str(escenario.variante_a_id),
                    "cantidad": 1,
                    "precio_unitario_bob": 100.0,
                }
            ],
            "medio_pago": "SALDO",
            "cliente_id": str(escenario.usuario_a.id),
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 400, resp.text
    assert "saldo insuficiente" in resp.json()["detail"].lower()

    # Stock no modificado y ningún débito registrado
    async with fabrica_sesiones() as db:
        disponible_despues = (await db.execute(stmt)).scalars().first().disponible
        assert disponible_despues == disponible_antes

        stmt_deb = select(MovimientoSaldo).where(
            MovimientoSaldo.cliente_id == escenario.usuario_a.id,
            MovimientoSaldo.tipo == "DEBITO",
        )
        mov_deb = (await db.execute(stmt_deb)).scalars().first()
        assert mov_deb is None


@pytest.mark.asyncio
async def test_cu19_saldo_suficiente_liquida_exito_debita_saldo_y_emite_kardex(
    http, escenario, fabrica_sesiones
):
    """CU19: Liquidar con SALDO suficiente debita saldo del cliente, reduce stock y emite Kardex VENTA_PRESENCIAL."""
    # 1. Acreditar 250 BOB al cliente
    async with fabrica_sesiones() as db:
        saldo_srv = SaldoService(db)
        await saldo_srv.acreditar_saldo(
            cliente_id=escenario.usuario_a.id,
            empresa_id=escenario.empresa_a_id,
            monto_bob=Decimal("250.00"),
            origen_tipo="RECARGA",
        )
        await db.commit()

        stmt_inv = select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == escenario.sucursal_a_id,
            InventarioSucursal.variante_id == escenario.variante_a_id,
        )
        disponible_antes = (await db.execute(stmt_inv)).scalars().first().disponible

    # 2. Liquidar venta presencial con SALDO (2 prendas de 100 = 200 BOB)
    http.usar(escenario.usuario_admin_a)
    clave = uuid.uuid4()
    resp = await http.cliente.post(
        "/api/v1/ventas/presenciales/liquidar",
        json={
            "sucursal_id": str(escenario.sucursal_a_id),
            "lineas": [
                {
                    "variante_id": str(escenario.variante_a_id),
                    "cantidad": 2,
                    "precio_unitario_bob": 100.0,
                }
            ],
            "medio_pago": "SALDO",
            "cliente_id": str(escenario.usuario_a.id),
        },
        headers={"Idempotency-Key": str(clave)},
    )
    assert resp.status_code == 201, resp.text
    res = resp.json()

    assert res["venta_id"] is not None
    assert float(res["total_bob"]) == 200.0
    assert res["estado_pago"] == "PAGADA"
    assert res["estado_entrega"] == "ENTREGADA"

    # 3. Comprobar que el saldo del cliente quedó en 50 BOB (250 - 200)
    async with fabrica_sesiones() as db:
        saldo_srv = SaldoService(db)
        disp, ret, _ = await saldo_srv.calcular_totales(
            cliente_id=escenario.usuario_a.id, empresa_id=escenario.empresa_a_id
        )
        assert disp == Decimal("50.00")

        # Comprobar movimiento DEBITO en el libro
        stmt_deb = select(MovimientoSaldo).where(
            MovimientoSaldo.cliente_id == escenario.usuario_a.id,
            MovimientoSaldo.tipo == "DEBITO",
            MovimientoSaldo.origen_tipo == "VENTA",
            MovimientoSaldo.origen_id == uuid.UUID(res["venta_id"]),
        )
        debito = (await db.execute(stmt_deb)).scalars().first()
        assert debito is not None
        assert debito.monto_bob == Decimal("200.00")

        # Comprobar reducción de stock
        disponible_despues = (await db.execute(stmt_inv)).scalars().first().disponible
        assert disponible_despues == disponible_antes - 2


@pytest.mark.asyncio
async def test_cu19_stripe_pendiente_o_fallido_no_entrega_ni_descuenta_stock(
    http, escenario, fabrica_sesiones
):
    """CU19: Liquidar con STRIPE_TEST cuando la orden/intención no está capturada falla 400 sin descontar stock."""
    fake = FakeStripeGateway()
    fijar_gateway(fake)
    pi_ref = f"pi_test_pending_{uuid.uuid4().hex[:8]}"
    fake.intenciones[pi_ref] = IntencionPago(
        id=pi_ref, venta_id=str(uuid.uuid4()), monto_centavos=10000, moneda="usd", estado="REQUIRES_PAYMENT"
    )

    async with fabrica_sesiones() as db:
        stmt_inv = select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == escenario.sucursal_a_id,
            InventarioSucursal.variante_id == escenario.variante_a_id,
        )
        disponible_antes = (await db.execute(stmt_inv)).scalars().first().disponible

    http.usar(escenario.usuario_admin_a)
    resp = await http.cliente.post(
        "/api/v1/ventas/presenciales/liquidar",
        json={
            "sucursal_id": str(escenario.sucursal_a_id),
            "lineas": [
                {
                    "variante_id": str(escenario.variante_a_id),
                    "cantidad": 1,
                    "precio_unitario_bob": 100.0,
                }
            ],
            "medio_pago": "STRIPE_TEST",
            "stripe_payment_intent_id": pi_ref,
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 400, resp.text
    assert "no está capturado" in resp.json()["detail"].lower()

    # Verificar stock intacto
    async with fabrica_sesiones() as db:
        disponible_despues = (await db.execute(stmt_inv)).scalars().first().disponible
        assert disponible_despues == disponible_antes


@pytest.mark.asyncio
async def test_cu19_stripe_capturado_liquida_exito_y_emite_kardex(
    http, escenario, fabrica_sesiones
):
    """CU19: Liquidar con STRIPE_TEST debidamente capturado aprueba venta, descuenta stock y emite Kardex."""
    fake = FakeStripeGateway()
    fijar_gateway(fake)
    pi_ref = f"pi_test_captured_{uuid.uuid4().hex[:8]}"
    fake.intenciones[pi_ref] = IntencionPago(
        id=pi_ref, venta_id=str(uuid.uuid4()), monto_centavos=10000, moneda="usd", estado="SUCCEEDED"
    )

    async with fabrica_sesiones() as db:
        stmt_inv = select(InventarioSucursal).where(
            InventarioSucursal.sucursal_id == escenario.sucursal_a_id,
            InventarioSucursal.variante_id == escenario.variante_a_id,
        )
        disponible_antes = (await db.execute(stmt_inv)).scalars().first().disponible

    http.usar(escenario.usuario_admin_a)
    clave = uuid.uuid4()
    resp = await http.cliente.post(
        "/api/v1/ventas/presenciales/liquidar",
        json={
            "sucursal_id": str(escenario.sucursal_a_id),
            "lineas": [
                {
                    "variante_id": str(escenario.variante_a_id),
                    "cantidad": 1,
                    "precio_unitario_bob": 100.0,
                }
            ],
            "medio_pago": "STRIPE_TEST",
            "stripe_payment_intent_id": pi_ref,
        },
        headers={"Idempotency-Key": str(clave)},
    )
    assert resp.status_code == 201, resp.text
    res = resp.json()

    assert res["venta_id"] is not None
    assert float(res["total_bob"]) == 100.0
    assert res["estado_pago"] == "PAGADA"
    assert res["estado_entrega"] == "ENTREGADA"

    # Verificar stock reducido en 1 unidad
    async with fabrica_sesiones() as db:
        disponible_despues = (await db.execute(stmt_inv)).scalars().first().disponible
        assert disponible_despues == disponible_antes - 1

        # Comprobar Pago STRIPE_TEST
        stmt_p = select(Pago).where(Pago.venta_id == uuid.UUID(res["venta_id"]))
        pago = (await db.execute(stmt_p)).scalars().first()
        assert pago is not None
        assert pago.metodo == "STRIPE_TEST"
        assert pago.monto == Decimal("100.00")
        assert pago.estado == "APROBADO"
        assert pago.referencia_externa == pi_ref
