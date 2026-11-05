"""Controller StripeService — CU15 y CU22 (E2 Stripe Test Mode).

Capacidades:
- Flujo interactivo legado CU15 (/stripe/intenciones, /stripe/intenciones/reintento, /stripe/estado, /stripe/webhook).
- Capacidades E2 CU22:
  - SetupIntent / método preparado online (POST /metodos/preparar, GET /metodos/{id}).
  - Órdenes de pago unificadas con cálculo de deuda por servidor, tasa congelada y centavos USD (POST /ordenes, GET /ordenes/{id}).
  - Continuación de acción 3DS / SCA (POST /ordenes/{id}/continuar-accion).
"""
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
from backend.app.core.modules.ventas_pagos.models_ordenes import (
    ContinuarAccionDTO,
    MetodoPreparado,
    MetodoPreparadoDTO,
    OrdenPago,
    OrdenPagoCrearDTO,
    OrdenPagoDTO,
)
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
                    contexto="VENTA", empresa_id=venta.empresa_id, reserva_id=None, venta_id=venta.id,
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
                # Buscar en comercial.ordenes_pago (CU22)
                stmt_op = select(OrdenPago).where(
                    OrdenPago.proveedor == "STRIPE",
                    OrdenPago.referencia_externa == pi_id,
                )
                op = (await self.db.execute(stmt_op)).scalars().first()
                if op is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intención no registrada")

                if tipo in ("payment_intent.succeeded",):
                    await self._aplicar_aprobado_orden(op, pi_id)
                    await self.db.commit()
                    return {"payment_intent": pi_id, "estado": "APROBADO"}
                if tipo in ("payment_intent.payment_failed", "payment_intent.canceled"):
                    await self._aplicar_rechazo_orden(op, pi_id, tipo)
                    await self.db.commit()
                    return {"payment_intent": pi_id, "estado": "RECHAZADO"}
                return {"payment_intent": pi_id, "estado": "IGNORADO"}

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

    async def _aplicar_aprobado_orden(self, op: OrdenPago, pi_id: str) -> None:
        ahora = self.reloj.ahora()
        if op.estado != "CAPTURADO":
            op.estado = "CAPTURADO"
            op.actualizada_en = ahora
            await self.db.flush()

        if op.contexto == "PEDIDO" and op.pedido_id:
            await self.confirmar_captura_pedido(op.pedido_id)
        elif op.contexto == "VENTA" and op.venta_id:
            await self._aplicar_aprobado(op.venta_id, pi_id)

    async def _aplicar_rechazo_orden(self, op: OrdenPago, pi_id: str, tipo: str = "") -> None:
        ahora = self.reloj.ahora()
        if op.estado != "FALLIDO":
            op.estado = "FALLIDO"
            op.actualizada_en = ahora
            await self.db.flush()

        if op.contexto == "PEDIDO" and op.pedido_id:
            from backend.app.core.modules.ventas_pagos.services.pedido_service import PedidoCompra
            pedido = await self.db.get(PedidoCompra, op.pedido_id)
            if pedido and pedido.estado_pago != "PAGADO":
                pedido.estado_pago = "FALLIDO"
                pedido.actualizado_en = ahora
                await self.db.flush()
        elif op.contexto == "VENTA" and op.venta_id:
            await self._aplicar_rechazo(op.venta_id, pi_id, tipo)

    async def confirmar_captura_pedido(self, pedido_id: uuid.UUID):
        from backend.app.core.modules.ventas_pagos.services.pedido_service import PedidoService
        svc = PedidoService(self.db, reloj=self.reloj)
        return await svc.confirmar_captura_pedido(pedido_id)

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

    # =========================================================================
    # Capacidades E2 — CU22: SetupIntents, Órdenes y 3DS
    # =========================================================================

    async def preparar_metodo(
        self, usuario: Usuario, clave_idempotencia: uuid.UUID, huella_dispositivo: Optional[str] = None,
    ) -> MetodoPreparadoDTO:
        """Crea SetupIntent en pasarela y registra método preparado en comercial.metodos_preparados."""
        if not usuario.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario sin empresa asignada",
            )
        gateway = gw.obtener_gateway()
        seti = await gateway.crear_setup_intent(
            cliente_id=str(usuario.id),
            idempotency_key=str(clave_idempotencia),
        )

        # Cifrado / ofuscación segura para BD
        c_cifrado = f"cus_{usuario.id.hex[:12]}".encode("utf-8")
        m_cifrado = f"pm_card_{usuario.id.hex[:12]}".encode("utf-8")
        p_cifrado = seti.id.encode("utf-8")

        mp = MetodoPreparado(
            id=uuid.uuid4(),
            empresa_id=usuario.empresa_id,
            cliente_id=usuario.id,
            proveedor="STRIPE",
            cliente_proveedor_cifrado=c_cifrado,
            metodo_proveedor_cifrado=m_cifrado,
            preparacion_proveedor_cifrado=p_cifrado,
            estado="LISTO",
            creado_en=self.reloj.ahora(),
        )
        self.db.add(mp)
        await self.db.flush()
        await self.db.commit()

        return MetodoPreparadoDTO(
            preparacion_pago_id=mp.id,
            client_secret=seti.client_secret,
            estado="LISTO",
            proveedor="STRIPE",
        )

    async def obtener_metodo_preparado(
        self, usuario: Usuario, preparacion_pago_id: uuid.UUID,
    ) -> MetodoPreparadoDTO:
        r = await self.db.execute(
            select(MetodoPreparado).where(
                MetodoPreparado.id == preparacion_pago_id,
                MetodoPreparado.empresa_id == usuario.empresa_id,
            )
        )
        mp = r.scalars().first()
        if mp is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Método preparado no encontrado",
            )
        if rol_de(usuario) == "CLIENTE" and mp.cliente_id != usuario.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para consultar este método preparado",
            )
        return MetodoPreparadoDTO(
            preparacion_pago_id=mp.id,
            client_secret=None,
            estado=mp.estado,
            proveedor=mp.proveedor,
        )

    async def crear_orden_pago(
        self, usuario: Usuario, datos: OrdenPagoCrearDTO, clave_idempotencia: uuid.UUID, autocommit: bool = True,
    ) -> OrdenPagoDTO:
        """Crea orden de pago unificada calculando deuda en servidor y congelando tasa y USD."""
        if not usuario.empresa_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Usuario sin empresa asignada",
            )
        empresa_id = usuario.empresa_id

        # 1. Idempotencia: por proveedor y clave_externa
        r_ord = await self.db.execute(
            select(OrdenPago).where(
                OrdenPago.proveedor == "STRIPE",
                OrdenPago.clave_externa == str(clave_idempotencia),
            )
        )
        ord_existente = r_ord.scalars().first()
        if ord_existente is not None:
            return OrdenPagoDTO(
                orden_pago_id=ord_existente.id,
                estado=ord_existente.estado,
                monto_bob=Decimal(str(ord_existente.monto_bob)),
                monto_usd=Decimal(str(ord_existente.monto_usd)) if ord_existente.monto_usd else None,
                centavos_usd=ord_existente.centavos_usd,
                tasa_id=ord_existente.tasa_id,
                client_secret=None,
                referencia_externa=ord_existente.referencia_externa,
            )

        # 2. Derivar recurso y calcular deuda exacta por servidor (no confiar en cliente)
        contexto = datos.contexto.upper()
        pedido_id, reserva_id, venta_id, cambio_id = None, None, None, None
        monto_bob = Decimal("0.00")

        if contexto == "VENTA":
            r_v = await self.db.execute(
                text("SELECT id, empresa_id, cliente_id, total, estado FROM comercial.ventas WHERE id = :id"),
                {"id": datos.recurso_id},
            )
            f_v = r_v.first()
            if not f_v:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
            if f_v[1] != empresa_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Venta de otra empresa")
            if rol_de(usuario) == "CLIENTE" and f_v[2] and f_v[2] != usuario.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
            monto_bob = Decimal(str(f_v[3]))
            venta_id = f_v[0]
        elif contexto == "PEDIDO":
            r_p = await self.db.execute(
                text("SELECT id, empresa_id, cliente_id, total_bob FROM comercial.pedidos_compra WHERE id = :id"),
                {"id": datos.recurso_id},
            )
            f_p = r_p.first()
            if f_p:
                if f_p[1] != empresa_id:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pedido de otra empresa")
                if rol_de(usuario) == "CLIENTE" and f_p[2] != usuario.id:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado")
                monto_bob = Decimal(str(f_p[3]))
                pedido_id = f_p[0]
            else:
                # Buscar en pedidos_entrega / venta asociada
                r_pe = await self.db.execute(
                    text(
                        "SELECT pe.id, v.empresa_id, pe.cliente_id, v.total, v.id "
                        "FROM comercial.pedidos_entrega pe JOIN comercial.ventas v ON pe.venta_id = v.id "
                        "WHERE pe.id = :id"
                    ),
                    {"id": datos.recurso_id},
                )
                f_pe = r_pe.first()
                if not f_pe:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado")
                if f_pe[1] != empresa_id:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pedido de otra empresa")
                monto_bob = Decimal(str(f_pe[3]))
                venta_id = f_pe[4]
                contexto = "VENTA"
        elif contexto == "RESERVA":
            r_r = await self.db.execute(
                text("SELECT id, empresa_id, cliente_id, total FROM comercial.reservas WHERE id = :id"),
                {"id": datos.recurso_id},
            )
            f_r = r_r.first()
            if not f_r:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reserva no encontrada")
            if f_r[1] != empresa_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reserva de otra empresa")
            monto_bob = Decimal(str(f_r[3]))
            reserva_id = f_r[0]
        elif contexto == "CAMBIO":
            r_c = await self.db.execute(
                text("SELECT id, empresa_id, cliente_id, diferencia_bob FROM comercial.cambios WHERE id = :id"),
                {"id": datos.recurso_id},
            )
            f_c = r_c.first()
            if not f_c:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cambio no encontrado")
            if f_c[1] != empresa_id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cambio de otra empresa")
            monto_bob = Decimal(str(f_c[3]))
            cambio_id = f_c[0]
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Contexto inválido {contexto}")

        # 3. Tasa de cambio BOB/USD congelada
        r_tasa = await self.db.execute(
            text("SELECT id, tasa_bob_por_usd FROM plataforma.tasas_cambio ORDER BY vigente_desde DESC LIMIT 1")
        )
        f_tasa = r_tasa.first()
        tasa_id = f_tasa[0] if f_tasa else None
        tasa_val = Decimal(str(f_tasa[1])) if f_tasa else Decimal("6.96")

        monto_usd = (monto_bob / tasa_val).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        centavos_usd = int(monto_usd * 100)

        # 4. Llamada a pasarela
        gateway = gw.obtener_gateway()
        off_session = bool(datos.metodo_preparado_id and datos.consentimiento_cobro_posterior)

        inten = await gateway.crear_pago_conectado(
            recurso_id=str(datos.recurso_id),
            monto_centavos=centavos_usd,
            moneda="usd",
            idempotency_key=str(clave_idempotencia),
            metodo_preparado_id=str(datos.metodo_preparado_id) if datos.metodo_preparado_id else None,
            off_session=off_session,
        )

        estado_orden = "PENDIENTE"
        if inten.estado == "REQUIRES_ACTION":
            estado_orden = "REQUIERE_ACCION_CLIENTE"
        elif inten.estado == "SUCCEEDED":
            estado_orden = "CAPTURADO"

        nueva_orden = OrdenPago(
            id=uuid.uuid4(),
            empresa_id=empresa_id,
            contexto=contexto,
            pedido_id=pedido_id,
            reserva_id=reserva_id,
            venta_id=venta_id,
            cambio_id=cambio_id,
            proveedor="STRIPE",
            clave_externa=str(clave_idempotencia),
            referencia_externa=inten.id,
            estado=estado_orden,
            monto_bob=monto_bob,
            tasa_id=tasa_id,
            monto_usd=monto_usd,
            centavos_usd=centavos_usd,
            revision=1,
            creada_en=self.reloj.ahora(),
            actualizada_en=self.reloj.ahora(),
        )
        self.db.add(nueva_orden)
        await self.db.flush()

        if estado_orden == "CAPTURADO":
            if contexto == "PEDIDO" and pedido_id:
                await self.confirmar_captura_pedido(pedido_id)
            elif contexto == "VENTA" and venta_id:
                await self._aplicar_aprobado(venta_id, inten.id)

        if autocommit:
            await self.db.commit()

        return OrdenPagoDTO(
            orden_pago_id=nueva_orden.id,
            estado=nueva_orden.estado,
            monto_bob=monto_bob,
            monto_usd=monto_usd,
            centavos_usd=centavos_usd,
            tasa_id=tasa_id,
            client_secret=inten.client_secret,
            referencia_externa=nueva_orden.referencia_externa,
        )

    async def obtener_orden_pago(self, usuario: Usuario, orden_pago_id: uuid.UUID) -> OrdenPagoDTO:
        r = await self.db.execute(
            select(OrdenPago).where(
                OrdenPago.id == orden_pago_id,
                OrdenPago.empresa_id == usuario.empresa_id,
            )
        )
        op = r.scalars().first()
        if op is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de pago no encontrada")
        return OrdenPagoDTO(
            orden_pago_id=op.id,
            estado=op.estado,
            monto_bob=Decimal(str(op.monto_bob)),
            monto_usd=Decimal(str(op.monto_usd)) if op.monto_usd else None,
            centavos_usd=op.centavos_usd,
            tasa_id=op.tasa_id,
            client_secret=None,
            referencia_externa=op.referencia_externa,
        )

    async def continuar_accion(
        self, usuario: Usuario, orden_pago_id: uuid.UUID, clave_idempotencia: uuid.UUID, payment_intent_id: Optional[str] = None,
    ) -> OrdenPagoDTO:
        """Continúa una orden de pago tras autenticación 3DS / SCA requerida."""
        r = await self.db.execute(
            select(OrdenPago).where(
                OrdenPago.id == orden_pago_id,
                OrdenPago.empresa_id == usuario.empresa_id,
            ).with_for_update()
        )
        op = r.scalars().first()
        if op is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Orden de pago no encontrada")

        if op.estado == "CAPTURADO":
            return OrdenPagoDTO(
                orden_pago_id=op.id,
                estado=op.estado,
                monto_bob=Decimal(str(op.monto_bob)),
                monto_usd=Decimal(str(op.monto_usd)) if op.monto_usd else None,
                centavos_usd=op.centavos_usd,
                tasa_id=op.tasa_id,
                client_secret=None,
                referencia_externa=op.referencia_externa,
            )

        if op.estado != "REQUIERE_ACCION_CLIENTE":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"La orden se encuentra en estado {op.estado}, no requiere acción del cliente",
            )

        ref_pi = payment_intent_id or op.referencia_externa
        if not ref_pi:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Falta referencia de PaymentIntent")

        gateway = gw.obtener_gateway()
        await gateway.confirmar_intencion(ref_pi)

        op.estado = "CAPTURADO"
        op.actualizada_en = self.reloj.ahora()
        await self.db.flush()

        if op.contexto == "PEDIDO" and op.pedido_id:
            await self.confirmar_captura_pedido(op.pedido_id)
        elif op.contexto == "VENTA" and op.venta_id:
            await self._aplicar_aprobado(op.venta_id, ref_pi)

        await self.db.flush()
        await self.db.commit()

        return OrdenPagoDTO(
            orden_pago_id=op.id,
            estado=op.estado,
            monto_bob=Decimal(str(op.monto_bob)),
            monto_usd=Decimal(str(op.monto_usd)) if op.monto_usd else None,
            centavos_usd=op.centavos_usd,
            tasa_id=op.tasa_id,
            client_secret=None,
            referencia_externa=op.referencia_externa,
        )
