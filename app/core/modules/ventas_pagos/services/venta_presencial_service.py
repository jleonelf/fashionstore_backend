"""Servicio de Venta Presencial Conectada en Caja — CU19.

Liquida pagos en EFECTIVO, SALDO o STRIPE_TEST, bloquea stock de forma atómica
y emite Kardex VENTA_PRESENCIAL único por ítem con emisión de comprobante.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import string
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional, Tuple

from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.idempotencia import hash_payload, resolver_idempotencia
from backend.app.core.modules.catalogo.models import VarianteProducto
from backend.app.core.modules.catalogo.services.promocion_service import PromocionService
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.inventario.models import InventarioSucursal, MovimientoInventario
from backend.app.core.modules.inventario.repositories.inventario_repository import InventarioRepository
from backend.app.core.modules.inventario.repositories.movimiento_repository import MovimientoRepository
from backend.app.core.modules.organizacion.models import Sucursal
from backend.app.core.modules.posventa.services.saldo_service import SaldoService
from backend.app.core.modules.ventas_pagos.integraciones import stripe_gateway as gw
from backend.app.core.modules.ventas_pagos.models import DetalleVenta, Pago, Venta
from backend.app.core.modules.ventas_pagos.models_ordenes import OrdenPago
from backend.app.core.modules.ventas_pagos.services.pedido_service import Comprobante
from backend.app.core.permisos import es_admin, exigir_sucursal
from backend.app.core.reloj import RelojSistema

NUMERO_ALFABETO = string.ascii_uppercase + string.digits


def _ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


# ============================================================================
# DTOs PYDANTIC
# ============================================================================

class LineaVentaPresencialDTO(BaseModel):
    variante_id: uuid.UUID
    cantidad: int = Field(gt=0, description="Cantidad mayor a cero")
    precio_unitario_bob: Optional[Decimal] = None
    descuento_bob: Optional[Decimal] = Field(default=Decimal("0.00"))


class VentaPresencialLiquidarDTO(BaseModel):
    sucursal_id: uuid.UUID
    lineas: List[LineaVentaPresencialDTO] = Field(min_length=1, description="Al menos un ítem a vender")
    medio_pago: Literal["EFECTIVO", "SALDO", "STRIPE_TEST"]
    cliente_id: Optional[uuid.UUID] = None
    efectivo_recibido_bob: Optional[Decimal] = None
    saldo_aplicado_bob: Optional[Decimal] = None
    stripe_payment_intent_id: Optional[str] = None
    turno_caja_id: Optional[uuid.UUID] = None


class VentaLiquidadaDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    venta_id: uuid.UUID
    numero: str
    total_bob: Decimal
    comprobante_id: uuid.UUID
    kardex_ids: List[uuid.UUID]
    cambio_entregado_bob: Decimal = Field(default=Decimal("0.00"))
    estado_pago: str = "PAGADA"
    estado_entrega: str = "ENTREGADA"
    fecha_hora: datetime


# ============================================================================
# SERVICIO VENTA PRESENCIAL
# ============================================================================

class VentaPresencialService:
    def __init__(self, db: AsyncSession, reloj=None):
        self.db = db
        self.reloj = reloj or RelojSistema()
        self.inventario_repo = InventarioRepository(db)
        self.movimiento_repo = MovimientoRepository(db)

    def _autorizar_caja(self, usuario: Usuario, sucursal_id: uuid.UUID) -> None:
        rol = (usuario.rol.nombre if usuario.rol else "").upper()
        if rol == "CAJERO":
            exigir_sucursal(usuario, sucursal_id)
            return
        if es_admin(usuario):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo Cajero asignado a la sucursal o Administrador pueden liquidar ventas presenciales",
        )

    async def _generar_numero_venta(self) -> str:
        for _ in range(5):
            num = "VTA-" + "".join(secrets.choice(NUMERO_ALFABETO) for _ in range(8))
            stmt = select(Venta.id).where(Venta.numero == num)
            if (await self.db.execute(stmt)).scalars().first() is None:
                return num
        raise HTTPException(status_code=500, detail="No se pudo generar un número de venta único")

    async def liquidar(
        self, usuario: Usuario, dto: VentaPresencialLiquidarDTO, clave: uuid.UUID
    ) -> VentaLiquidadaDTO:
        digest = hash_payload(dto.model_dump(mode="json"))

        # Idempotencia previa
        reintento = await resolver_idempotencia(self.db, Venta, clave, digest)
        if reintento is not None:
            return await self._a_venta_liquidada_dto(reintento)

        self._autorizar_caja(usuario, dto.sucursal_id)

        if not usuario.empresa_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Usuario sin empresa asignada")

        sucursal = await self.db.get(Sucursal, dto.sucursal_id)
        if sucursal is None or sucursal.empresa_id != usuario.empresa_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada en la empresa")
        if not sucursal.activa:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sucursal inactiva")

        # Validar variantes únicas en solicitud
        variantes_solicitadas = set()
        for item in dto.lineas:
            if item.variante_id in variantes_solicitadas:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Variante duplicada en la venta")
            variantes_solicitadas.add(item.variante_id)

        # 1. Bloqueo determinista de inventario ordenado por (sucursal_id, variante_id)
        claves_ordenadas = sorted([(dto.sucursal_id, vid) for vid in variantes_solicitadas], key=lambda x: str(x[1]))
        filas_inv = await self.inventario_repo.bloquearFilas(claves_ordenadas)

        ahora = self.reloj.ahora()
        subtotal = Decimal("0.00")
        descuento_total = Decimal("0.00")
        planes_items = []

        promocion_service = PromocionService(self.db, self.reloj)
        saldo_service = SaldoService(self.db, self.reloj)

        for item in dto.lineas:
            var = await self.db.get(VarianteProducto, item.variante_id)
            if var is None or var.empresa_id != usuario.empresa_id:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Variante {item.variante_id} no encontrada")

            fila_stock = filas_inv.get((dto.sucursal_id, item.variante_id))
            if fila_stock is None or fila_stock.disponible < item.cantidad:
                disponible_actual = fila_stock.disponible if fila_stock else 0
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Stock insuficiente para variante {item.variante_id}: disponible {disponible_actual}, requerido {item.cantidad}",
                )

            # Precios y promociones calculados EXCLUSIVAMENTE por el servidor
            precio_servidor = Decimal(str(var.precio or 0))
            desc_servidor, promo_id = await promocion_service.mejorDescuento(
                var.id, precio_servidor, item.cantidad, ahora
            )

            # Rechazo explícito si el cliente/caja envió precio adulterado
            if item.precio_unitario_bob is not None:
                precio_cliente = Decimal(str(item.precio_unitario_bob))
                if abs(precio_cliente - precio_servidor) > Decimal("0.01"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Precio unitario adulterado o desactualizado para la variante {item.variante_id}: enviado {item.precio_unitario_bob}, servidor {precio_servidor}",
                    )

            # Rechazo explícito si el cliente/caja envió descuento adulterado
            if item.descuento_bob is not None:
                desc_cliente = Decimal(str(item.descuento_bob))
                if abs(desc_cliente - desc_servidor) > Decimal("0.01"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Descuento adulterado o desactualizado para la variante {item.variante_id}: enviado {item.descuento_bob}, servidor {desc_servidor}",
                    )

            precio = precio_servidor
            desc = desc_servidor
            costo = Decimal(str(var.costo_promedio or 0))

            tot_item = (precio * item.cantidad) - desc
            subtotal += precio * item.cantidad
            descuento_total += desc
            planes_items.append((var, item.cantidad, precio, desc, tot_item, costo, fila_stock, promo_id))

        total = subtotal - descuento_total
        if total < Decimal("0.00"):
            total = Decimal("0.00")

        # 2. Liquidación del medio de pago (VERIFICACIÓN PREVIA ANTES DE DESCONTAR STOCK)
        cambio_entregado = Decimal("0.00")
        orden_stripe: Optional[OrdenPago] = None

        if dto.medio_pago == "EFECTIVO":
            recibido = dto.efectivo_recibido_bob or Decimal("0.00")
            if recibido < total:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Efectivo recibido ({recibido} BOB) es menor al total adeudado ({total} BOB)",
                )
            cambio_entregado = recibido - total
        elif dto.medio_pago == "SALDO":
            if not dto.cliente_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Venta con saldo requiere cliente_id")
            disp, _, _ = await saldo_service.calcular_totales(
                cliente_id=dto.cliente_id, empresa_id=usuario.empresa_id, con_bloqueo=True
            )
            if total > disp:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Saldo insuficiente: disponible {disp} BOB, requerido {total} BOB",
                )
        elif dto.medio_pago == "STRIPE_TEST":
            if not dto.stripe_payment_intent_id or not dto.stripe_payment_intent_id.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Venta con STRIPE_TEST requiere stripe_payment_intent_id",
                )
            # 1. Comprobar orden de pago en base de datos si existe
            stmt_orden = select(OrdenPago).where(
                OrdenPago.empresa_id == usuario.empresa_id,
                (OrdenPago.referencia_externa == dto.stripe_payment_intent_id)
                | (OrdenPago.clave_externa == dto.stripe_payment_intent_id),
            )
            orden_stripe = (await self.db.execute(stmt_orden)).scalars().first()
            if orden_stripe is not None:
                if orden_stripe.estado != "CAPTURADO":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"La orden de pago Stripe no está capturada (estado: {orden_stripe.estado})",
                    )
                if Decimal(str(orden_stripe.monto_bob)) < total:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Monto de orden Stripe ({orden_stripe.monto_bob} BOB) es menor al total adeudado ({total} BOB)",
                    )
            else:
                # 2. Consultar Gateway de Stripe
                try:
                    gateway = gw.obtener_gateway()
                    intencion = await gateway.consultar_intencion(dto.stripe_payment_intent_id)
                    if intencion.estado.upper() not in ("SUCCEEDED", "CAPTURADO"):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"El PaymentIntent de Stripe no está capturado (estado: {intencion.estado})",
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"No se pudo comprobar la liquidación en Stripe: {str(e)}",
                    )

        # 3. Descontar stock disponible atómicamente SOLO TRAS LIQUIDACIÓN VERIFICADA
        for var, cant, precio, desc, tot_item, costo, fila_stock, promo_id in planes_items:
            fila_stock.disponible -= cant
            await self.db.flush()

        # 4. Crear Venta
        numero_venta = await self._generar_numero_venta()
        venta = Venta(
            id=uuid.uuid4(),
            empresa_id=usuario.empresa_id,
            numero=numero_venta,
            cliente_id=dto.cliente_id,
            sucursal_id=dto.sucursal_id,
            cajero_id=usuario.id,
            canal="PRESENCIAL",
            estado="PAGADA",
            subtotal=subtotal,
            descuento=descuento_total,
            costo_entrega=Decimal("0.00"),
            total=total,
            creada_en=ahora,
            confirmada_en=ahora,
            entregada_en=ahora,
            clave_idempotencia=clave,
            hash_solicitud=digest,
            turno_caja_id=dto.turno_caja_id,
        )
        self.db.add(venta)
        await self.db.flush()

        # Si el medio de pago es SALDO, debitar formalmente del cliente
        if dto.medio_pago == "SALDO":
            await saldo_service.debitar_saldo(
                cliente_id=dto.cliente_id,
                empresa_id=usuario.empresa_id,
                monto_bob=total,
                origen_tipo="VENTA",
                origen_id=venta.id,
                referencia_unica=clave,
            )

        if orden_stripe is not None:
            orden_stripe.venta_id = venta.id
            orden_stripe.actualizada_en = ahora

        # 5. Detalles de Venta y Movimientos Kardex
        kardex_ids: List[uuid.UUID] = []
        detalles_comprobante = []

        for var, cant, precio, desc, tot_item, costo, fila_stock, promo_id in planes_items:
            det = DetalleVenta(
                id=uuid.uuid4(),
                venta_id=venta.id,
                variante_id=var.id,
                cantidad=cant,
                precio_unitario=precio,
                descuento=desc,
                costo_promedio=costo,
                promocion_id=promo_id,
            )
            self.db.add(det)
            await self.db.flush()

            # Kardex VENTA_PRESENCIAL único
            kardex_mov = MovimientoInventario(
                id=uuid.uuid4(),
                variante_id=var.id,
                sucursal_origen_id=dto.sucursal_id,
                sucursal_destino_id=dto.sucursal_id,
                responsable_id=usuario.id,
                tipo="VENTA_PRESENCIAL",
                cantidad=cant,
                costo_unitario=costo,
                referencia_tipo="VENTA",
                referencia_id=venta.id,
                linea_referencia_id=det.id,
                observacion=f"Venta presencial {numero_venta}",
                fecha_hora=ahora,
            )
            self.db.add(kardex_mov)
            await self.db.flush()
            kardex_ids.append(kardex_mov.id)

            detalles_comprobante.append(
                {
                    "variante_id": str(var.id),
                    "cantidad": cant,
                    "precio_unitario": str(precio),
                    "descuento": str(desc),
                    "subtotal": str(tot_item),
                }
            )

        # 6. Registrar Pago si aplica (para medios de pago financieros en comercial.pagos)
        if dto.medio_pago in ("EFECTIVO", "STRIPE_TEST"):
            pago = Pago(
                id=uuid.uuid4(),
                empresa_id=usuario.empresa_id,
                contexto="VENTA",
                venta_id=venta.id,
                metodo=dto.medio_pago,
                tipo_pago="TOTAL",
                monto=total,
                estado="APROBADO",
                efectivo_recibido_bob=dto.efectivo_recibido_bob if dto.medio_pago == "EFECTIVO" else None,
                cambio_entregado_bob=cambio_entregado if dto.medio_pago == "EFECTIVO" else None,
                referencia_externa=dto.stripe_payment_intent_id if dto.medio_pago == "STRIPE_TEST" else None,
                proveedor_pago="STRIPE_TEST" if dto.medio_pago == "STRIPE_TEST" else None,
                pagado_en=ahora,
                clave_idempotencia=None,
                hash_solicitud=digest,
            )
            self.db.add(pago)

        # 7. Registrar Comprobante
        doc_comprobante = {
            "venta_id": str(venta.id),
            "numero": numero_venta,
            "sucursal_id": str(dto.sucursal_id),
            "cajero_id": str(usuario.id),
            "cliente_id": str(dto.cliente_id) if dto.cliente_id else None,
            "lineas": detalles_comprobante,
            "total_bob": str(total),
            "medio_pago": dto.medio_pago,
            "efectivo_recibido_bob": str(dto.efectivo_recibido_bob or 0),
            "cambio_entregado_bob": str(cambio_entregado),
            "fecha_hora": ahora.isoformat(),
        }
        comprobante = Comprobante(
            id=uuid.uuid4(),
            empresa_id=usuario.empresa_id,
            tipo="VENTA_PRESENCIAL",
            recurso_tipo="VENTA",
            recurso_id=venta.id,
            version=1,
            documento=doc_comprobante,
            documento_hash=hashlib.sha256(json.dumps(doc_comprobante, sort_keys=True).encode("utf-8")).hexdigest(),
            creado_en=ahora,
        )
        self.db.add(comprobante)

        await self.db.commit()

        return VentaLiquidadaDTO(
            venta_id=venta.id,
            numero=venta.numero,
            total_bob=venta.total,
            comprobante_id=comprobante.id,
            kardex_ids=kardex_ids,
            cambio_entregado_bob=cambio_entregado,
            estado_pago=venta.estado if isinstance(venta.estado, str) else venta.estado.name,
            estado_entrega="ENTREGADA",
            fecha_hora=ahora,
        )

    async def _a_venta_liquidada_dto(self, venta: Venta) -> VentaLiquidadaDTO:
        stmt_comp = select(Comprobante).where(
            Comprobante.recurso_tipo == "VENTA",
            Comprobante.recurso_id == venta.id,
        )
        comp = (await self.db.execute(stmt_comp)).scalars().first()
        comp_id = comp.id if comp else venta.id

        stmt_k = select(MovimientoInventario.id).where(
            MovimientoInventario.referencia_tipo == "VENTA",
            MovimientoInventario.referencia_id == venta.id,
        )
        kardex_ids = list((await self.db.execute(stmt_k)).scalars().all())

        stmt_pago = select(Pago).where(Pago.venta_id == venta.id)
        pago = (await self.db.execute(stmt_pago)).scalars().first()
        cambio = pago.cambio_entregado_bob if pago and pago.cambio_entregado_bob is not None else Decimal("0.00")

        return VentaLiquidadaDTO(
            venta_id=venta.id,
            numero=venta.numero,
            total_bob=venta.total,
            comprobante_id=comp_id,
            kardex_ids=kardex_ids,
            cambio_entregado_bob=cambio,
            estado_pago=venta.estado if isinstance(venta.estado, str) else venta.estado.name,
            estado_entrega="ENTREGADA",
            fecha_hora=venta.confirmada_en or venta.creada_en,
        )
