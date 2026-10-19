"""Controller StripeService — CU15 (RF19, RN-05)."""
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.modules.ventas_pagos.integraciones import stripe_gateway as gw
from backend.app.core.config import settings
from backend.app.core.idempotencia import hash_payload
from backend.app.core.permisos import es_admin, rol_de
from backend.app.core.reloj import RelojSistema
from backend.app.core.modules.ventas_pagos.models import Pago, Venta
from backend.app.core.modules.inventario.models import MovimientoInventario
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.ventas_pagos.repositories.pedido_repository import PedidoRepository
from backend.app.core.modules.inventario.repositories.inventario_repository import InventarioRepository
from backend.app.core.modules.inventario.repositories.movimiento_repository import MovimientoRepository
from backend.app.core.modules.ventas_pagos.repositories.pago_repository import PagoRepository
from backend.app.core.modules.ventas_pagos.repositories.venta_repository import DetalleVentaRepository, VentaRepository
from backend.app.core.modules.ventas_pagos.schemas import EstadoPagoDTO, IntencionDTO


def _centavos(monto: Decimal) -> int:
    return int((Decimal(str(monto)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


class StripeService:
    def __init__(self, db: AsyncSession, reloj=None):
        self.db = db
        self.reloj = reloj or RelojSistema()
        self.venta_repo = VentaRepository(db)
        self.pago_repo = PagoRepository(db)
        self.detalle_repo = DetalleVentaRepository(db)
        self.pedido_repo = PedidoRepository(db)
        self.inventario_repo = InventarioRepository(db)
        self.movimiento_repo = MovimientoRepository(db)

    async def _venta_digital(self, venta_id: uuid.UUID) -> Venta:
        venta = await self.venta_repo.buscarPorId(venta_id)
        if venta is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
        if venta.canal not in ("WEB", "MOVIL"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Solo ventas digitales usan Stripe")
        return venta

    def _autorizar_intencion(self, usuario: Usuario, venta: Venta) -> None:
        if es_admin(usuario):
            return
        if rol_de(usuario) == "CLIENTE" and venta.cliente_id == usuario.id:
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo el propietario o el Administrador")

    async def crearIntencion(
        self, usuario: Usuario, venta_id: uuid.UUID, clave: uuid.UUID,
    ) -> Tuple[IntencionDTO, bool]:
        venta = await self._venta_digital(venta_id)
        self._autorizar_intencion(usuario, venta)
        estado = venta.estado if isinstance(venta.estado, str) else venta.estado.name
        if estado == "CANCELADA":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Venta cancelada: sin reintento")
        if estado == "PAGADA":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Venta ya pagada")
        if venta.expira_en is not None and venta.expira_en <= self.reloj.ahora():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ventana de pago vencida")
        if not settings.STRIPE_ENABLED or not settings.STRIPE_SECRET_KEY:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "codigo": "STRIPE_DESHABILITADO",
                    "mensaje": "Pasarela en modo prueba no configurada.",
                },
            )
        gw.exigir_test_mode()
        digest = hash_payload({"venta_id": str(venta_id)})
        try:
            existente = await self.pago_repo.buscarPorClave(clave)
            if existente is not None:
                if existente.hash_solicitud != digest:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={
                            "codigo": "IDEMPOTENCIA_CONFLICTO",
                            "mensaje": "Idempotency-Key ya usada con otra solicitud",
                        },
                    )
                return self._a_intencion(venta, existente), False
            pago_previo = await self._pago_stripe_de_venta(venta.id)
            gateway = gw.obtener_gateway()
            referencia: Optional[str] = pago_previo.referencia_externa if pago_previo else None
            if referencia:
                try:
                    pi_vigente = await gateway.consultar_intencion(referencia)
                    if pi_vigente.estado == "CANCELED":
                        referencia = None
                except HTTPException:
                    pass
            inten = await gateway.crear_o_reutilizar_intencion(
                venta_id=str(venta.id),
                monto_centavos=_centavos(venta.total),
                moneda=settings.STRIPE_CURRENCY or "usd",
                idempotency_key=str(clave),
                referencia_existente=referencia,
            )
            if pago_previo is not None:
                pago = pago_previo
                if pago.referencia_externa != inten.id:
                    pago.referencia_externa = inten.id
                    pago.estado = "PENDIENTE"
                    pago.pagado_en = None
                    await self.db.flush()
                elif pago.estado == "RECHAZADO":
                    pago.estado = "PENDIENTE"
                    await self.db.flush()
            else:
                pago = Pago(
                    contexto="VENTA", reserva_id=None, venta_id=venta.id,
                    metodo="STRIPE_TEST", tipo_pago="PAGO",
                    monto=venta.total, no_reembolsable=False, estado="PENDIENTE",
                    referencia_externa=inten.id, proveedor_pago="STRIPE_TEST",
                    clave_idempotencia=clave, hash_solicitud=digest,
                )
                await self.pago_repo.crear(pago)
            await self.db.commit()
            return self._a_intencion(venta, pago, client_secret=inten.client_secret), pago_previo is None
        except HTTPException:
            await self.db.rollback()
            raise
        except IntegrityError as e:
            await self.db.rollback()
            msg = str(getattr(e, "orig", e)).lower()
            if "clave_idempotencia" in msg or "uq_pagos_referencia_externa" in msg:
                pago = await self.pago_repo.buscarPorClave(clave) or await self._pago_stripe_de_venta(venta_id)
                if pago is not None:
                    if pago.hash_solicitud != digest and "clave_idempotencia" in msg:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="Idempotency-Key ya usada con otra solicitud",
                        )
                    venta_fresca = await self.venta_repo.buscarPorId(venta_id)
                    return self._a_intencion(venta_fresca, pago), False
            raise

    def _a_intencion(self, venta: Venta, pago: Pago, client_secret: Optional[str] = None) -> IntencionDTO:
        return IntencionDTO(
            payment_intent_id=pago.referencia_externa or "",
            venta_id=venta.id, monto=venta.total,
            moneda=settings.STRIPE_CURRENCY or "usd",
            estado=pago.estado, client_secret=client_secret,
        )

    async def _pago_stripe_de_venta(self, venta_id: uuid.UUID) -> Optional[Pago]:
        pagos = await self.pago_repo.pagosDeVenta(venta_id)
        for p in pagos:
            if p.metodo == "STRIPE_TEST":
                return p
        return None

    async def estado(self, usuario: Usuario, venta_id: uuid.UUID) -> EstadoPagoDTO:
        venta = await self._venta_digital(venta_id)
        self._autorizar_intencion(usuario, venta)
        pago = await self._pago_stripe_de_venta(venta.id)
        return EstadoPagoDTO(
            venta_id=venta.id,
            estado_venta=venta.estado if isinstance(venta.estado, str) else venta.estado.name,
            estado_pago=pago.estado if pago else "SIN_INTENCION",
            payment_intent_id=pago.referencia_externa if pago else None,
            monto=venta.total, expira_en=venta.expira_en,
        )

    async def confirmarWebhook(self, cuerpo_crudo: bytes, firma: Optional[str], evento: dict) -> dict:
        try:
            gw.verificar_firma_stripe(cuerpo_crudo, firma, settings.STRIPE_WEBHOOK_SECRET or "")
        except gw.FirmaStripeInvalida as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Firma inválida: {e}")
        if evento.get("livemode") is True:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "codigo": "STRIPE_MODO_NO_PERMITIDO",
                    "mensaje": "Evento live rechazado; solo Test Mode",
                },
            )
        tipo = str(evento.get("type", ""))
        tipos_soportados = {
            "payment_intent.succeeded",
            "payment_intent.payment_failed",
            "payment_intent.canceled",
        }
        if tipo not in tipos_soportados:
            return {"evento": tipo, "estado": "IGNORADO"}
        objeto = evento.get("data", {}).get("object", {}) if isinstance(evento.get("data"), dict) else {}
        pi_id = str(objeto.get("id", ""))
        if not pi_id:
            rel = evento.get("related_object", {}) if isinstance(evento.get("related_object"), dict) else {}
            pi_id = str(rel.get("id", ""))
        if not pi_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Evento sin payment_intent")
        try:
            pago = await self._pago_por_referencia(pi_id)
            if pago is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intención no registrada")
            if (pago.referencia_externa or "") != pi_id:
                return {"payment_intent": pi_id, "estado": "IGNORADO"}
            if tipo in ("payment_intent.succeeded",):
                await self._aplicar_aprobado(pago.venta_id, pi_id)
                await self.db.commit()
                return {"payment_intent": pi_id, "estado": "APROBADO"}
            if tipo in ("payment_intent.payment_failed", "payment_intent.canceled"):
                await self._aplicar_rechazo(pago.venta_id, pi_id, tipo)
                await self.db.commit()
                return {"payment_intent": pi_id, "estado": "RECHAZADO"}
            return {"payment_intent": pi_id, "estado": "IGNORADO"}
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise

    async def _pago_por_referencia(self, pi_id: str) -> Optional[Pago]:
        r = await self.db.execute(
            select(Pago).where(Pago.referencia_externa == pi_id, Pago.metodo == "STRIPE_TEST")
        )
        return r.scalars().first()

    async def _bloquear_venta(self, venta_id: uuid.UUID) -> Venta:
        await self.db.execute(
            select(Venta.id).where(Venta.id == venta_id).with_for_update()
        )
        venta = await self.venta_repo.buscarPorId(venta_id)
        if venta is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
        return venta

    @staticmethod
    def _estado(venta: Venta) -> str:
        return venta.estado if isinstance(venta.estado, str) else venta.estado.name

    async def _aplicar_aprobado(self, venta_id: uuid.UUID, pi_id: str) -> None:
        venta = await self._bloquear_venta(venta_id)
        estado = self._estado(venta)
        pago = await self._pago_por_referencia(pi_id)
        if pago is None:
            return
        if pago.estado == "APROBADO" and estado == "PAGADA":
            return
        if estado in ("CANCELADA", "DEVUELTA"):
            return
        if venta.expira_en is not None and venta.expira_en <= self.reloj.ahora() and estado != "PAGADA":
            return
        ahora = self.reloj.ahora()
        pago.estado = "APROBADO"
        pago.pagado_en = ahora
        await self.db.flush()
        detalles = await self.detalle_repo.porVenta(venta.id)
        claves = sorted(
            {(venta.sucursal_id, d.variante_id) for d in detalles},
            key=lambda c: (str(c[0]), str(c[1])),
        )
        filas = await self.inventario_repo.bloquearFilas(claves)
        for det in detalles:
            fila = filas.get((venta.sucursal_id, det.variante_id))
            if fila is None or fila.reservado < det.cantidad:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Compromiso insuficiente al confirmar el pago",
                )
            fila.reservado -= det.cantidad
            await self.db.flush()
            mov, _ = await self.movimiento_repo.registrarUnico(
                MovimientoInventario(
                    variante_id=det.variante_id,
                    sucursal_destino_id=venta.sucursal_id,
                    tipo="VENTA_DIGITAL",
                    cantidad=det.cantidad,
                    costo_unitario=det.costo_promedio,
                    referencia_tipo="VENTA",
                    referencia_id=venta.id,
                    linea_referencia_id=det.id,
                    observacion=f"Venta digital {venta.numero} aprobada ({pi_id})",
                )
            )
        venta.estado = "PAGADA"
        venta.confirmada_en = ahora
        await self.db.flush()
        pedido = await self.pedido_repo.buscarPorVenta(venta.id)
        if pedido is not None and pedido.estado == "SOLICITADO":
            pedido.estado = "PREPARADO"
            await self.db.flush()

    async def _aplicar_rechazo(self, venta_id: uuid.UUID, pi_id: str, tipo: str = "") -> None:
        venta = await self._bloquear_venta(venta_id)
        estado = self._estado(venta)
        pago = await self._pago_por_referencia(pi_id)
        if pago is None:
            return
        if pago.estado in ("APROBADO",):
            return
        if estado in ("PAGADA", "CANCELADA", "DEVUELTA"):
            return
        pago.estado = "RECHAZADO"
        await self.db.flush()

    async def cancelarVencidas(self, lote: int = 100) -> dict:
        import asyncio

        try:
            lock = await self.db.execute(select(text("pg_try_advisory_lock(9100315)")))
            tiene = bool(lock.scalar())
        except Exception:
            tiene = True
        if not tiene:
            return {"procesadas": 0, "canceladas": [], "omitidas": [], "bloqueo_activo": False}
        ahora = self.reloj.ahora()
        canceladas, omitidas, errores = [], [], []
        procesadas = 0
        for intento in range(5):
            r = await self.db.execute(
                text(
                    "SELECT id FROM comercial.ventas WHERE estado = 'PENDIENTE_PAGO' "
                    "AND expira_en IS NOT NULL AND expira_en <= :ahora "
                    "ORDER BY expira_en LIMIT :lote FOR UPDATE SKIP LOCKED"
                ),
                {"ahora": ahora, "lote": lote},
            )
            ids = [row[0] for row in r.all()]
            if not ids:
                restantes = await self.db.execute(
                    text(
                        "SELECT count(*) FROM comercial.ventas WHERE estado = 'PENDIENTE_PAGO' "
                        "AND expira_en IS NOT NULL AND expira_en <= :ahora"
                    ),
                    {"ahora": ahora},
                )
                if int(restantes.scalar() or 0) == 0:
                    break
                await asyncio.sleep(0.05 * (intento + 1))
                continue
            procesadas += len(ids)
        for vid in ids:
            try:
                venta = await self._bloquear_venta(uuid.UUID(str(vid)))
                if self._estado(venta) != "PENDIENTE_PAGO":
                    omitidas.append(str(vid))
                    continue
                detalles = await self.detalle_repo.porVenta(venta.id)
                claves = sorted(
                    {(venta.sucursal_id, d.variante_id) for d in detalles},
                    key=lambda c: (str(c[0]), str(c[1])),
                )
                filas = await self.inventario_repo.bloquearFilas(claves)
                for det in detalles:
                    fila = filas.get((venta.sucursal_id, det.variante_id))
                    if fila is not None and fila.reservado >= det.cantidad:
                        fila.reservado -= det.cantidad
                        fila.disponible += det.cantidad
                        await self.db.flush()
                    await self.movimiento_repo.registrarUnico(
                        MovimientoInventario(
                            variante_id=det.variante_id,
                            sucursal_destino_id=venta.sucursal_id,
                            tipo="LIBERACION_DIGITAL",
                            cantidad=det.cantidad,
                            costo_unitario=det.costo_promedio,
                            referencia_tipo="VENTA",
                            referencia_id=venta.id,
                            linea_referencia_id=det.id,
                            observacion=f"Liberación por vencimiento {venta.numero}",
                        )
                    )
                venta.estado = "CANCELADA"
                await self.db.flush()
                pago = await self._pago_stripe_de_venta(venta.id)
                if pago is not None and pago.estado == "PENDIENTE":
                    pago.estado = "ANULADO"
                    await self.db.flush()
                pedido = await self.pedido_repo.buscarPorVenta(venta.id)
                if pedido is not None and pedido.estado == "SOLICITADO":
                    pedido.estado = "CANCELADO"
                    await self.db.flush()
                await self.db.commit()
                canceladas.append(str(vid))
            except Exception as e:
                await self.db.rollback()
                errores.append({"venta_id": str(vid), "error": str(e)[:200]})
        try:
            await self.db.execute(select(text("pg_advisory_unlock(9100315)")))
        except Exception:
            pass
        return {
            "procesadas": procesadas, "canceladas": canceladas,
            "omitidas": omitidas, "errores": errores, "bloqueo_activo": True,
        }
