"""Puerta Stripe Test Mode — Ciclo 3 y E2 (CU15, CU22, CU27).

Sin claves la app inicia y este módulo responde 503 tipado; ninguna prueba
automática llama a Stripe real (usan FakeStripeGateway vía monkeypatch).
Con claves, el adaptador real usa httpx contra api.stripe.com (PaymentIntents, SetupIntents, Refunds)
y verifica el webhook con HMAC-SHA256 del cuerpo crudo (sin SDK obligatorio).
Nunca se almacena tarjeta/CVC: solo IDs (pi_*, seti_*, re_*) y estados.
"""
import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import HTTPException, status

from backend.app.core.config import settings


class StripeDeshabilitado(Exception):
    """Stripe sin configurar o apagado: el endpoint debe responder 503 tipado."""


class FirmaStripeInvalida(Exception):
    """La firma del webhook no verifica contra el cuerpo crudo."""


@dataclass
class IntencionPago:
    id: str
    venta_id: str
    monto_centavos: int
    moneda: str
    estado: str  # REQUIRES_PAYMENT | SUCCEEDED | FAILED | CANCELED | REQUIRES_ACTION
    client_secret: Optional[str] = None


@dataclass
class SetupIntentInfo:
    id: str
    cliente_id: str
    estado: str  # requires_payment_method | succeeded
    client_secret: Optional[str] = None


@dataclass
class ReembolsoInfo:
    id: str
    payment_intent_id: str
    centavos_usd: int
    estado: str  # succeeded | pending | failed


class StripeGateway:
    """Contrato del adaptador. Producción y fakes lo implementan."""

    async def crear_o_reutilizar_intencion(
        self, venta_id: str, monto_centavos: int, moneda: str,
        idempotency_key: str, referencia_existente: Optional[str] = None,
    ) -> IntencionPago:
        raise NotImplementedError

    async def consultar_intencion(self, payment_intent_id: str) -> IntencionPago:
        raise NotImplementedError

    async def crear_setup_intent(
        self, cliente_id: str, idempotency_key: Optional[str] = None,
    ) -> SetupIntentInfo:
        raise NotImplementedError

    async def crear_pago_conectado(
        self, recurso_id: str, monto_centavos: int, moneda: str,
        idempotency_key: str, metodo_preparado_id: Optional[str] = None,
        off_session: bool = False, simular_requiere_accion: bool = False,
    ) -> IntencionPago:
        raise NotImplementedError

    async def confirmar_intencion(self, payment_intent_id: str) -> IntencionPago:
        raise NotImplementedError

    async def crear_reembolso(
        self, payment_intent_id: str, centavos_usd: int, idempotency_key: Optional[str] = None,
    ) -> ReembolsoInfo:
        raise NotImplementedError


class FakeStripeGateway(StripeGateway):
    """Doble de pruebas: sin red, determinista, conmutado por tests."""

    def __init__(self):
        self.intenciones: dict[str, IntencionPago] = {}
        self.por_venta: dict[str, str] = {}
        self.setup_intents: dict[str, SetupIntentInfo] = {}
        self.reembolsos: dict[str, ReembolsoInfo] = {}
        self.simular_requiere_accion: bool = False

    async def crear_o_reutilizar_intencion(
        self, venta_id, monto_centavos, moneda, idempotency_key, referencia_existente=None,
    ) -> IntencionPago:
        # FAILED reutiliza el PI vigente; CANCELED exige uno nuevo porque un
        # PI cancelado ya no puede procesar un pago (contrato Stripe).
        if referencia_existente and referencia_existente in self.intenciones:
            vigente = self.intenciones[referencia_existente]
            if vigente.estado != "CANCELED":
                return vigente
        elif venta_id in self.por_venta:
            pi_id = self.por_venta[venta_id]
            vigente = self.intenciones.get(pi_id)
            if vigente is not None and vigente.estado != "CANCELED":
                return vigente
        pi_id = f"pi_test_{secrets.token_hex(4)}"
        inten = IntencionPago(
            id=pi_id, venta_id=venta_id, monto_centavos=monto_centavos,
            moneda=moneda, estado="REQUIRES_PAYMENT",
            client_secret=f"{pi_id}_secret_test",
        )
        self.intenciones[pi_id] = inten
        self.por_venta[venta_id] = pi_id
        return inten

    async def consultar_intencion(self, payment_intent_id: str) -> IntencionPago:
        if payment_intent_id not in self.intenciones:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intención no encontrada")
        return self.intenciones[payment_intent_id]

    async def crear_setup_intent(
        self, cliente_id: str, idempotency_key: Optional[str] = None,
    ) -> SetupIntentInfo:
        seti_id = f"seti_test_{secrets.token_hex(4)}"
        info = SetupIntentInfo(
            id=seti_id,
            cliente_id=cliente_id,
            estado="succeeded",
            client_secret=f"{seti_id}_secret_test",
        )
        self.setup_intents[seti_id] = info
        return info

    async def crear_pago_conectado(
        self, recurso_id: str, monto_centavos: int, moneda: str,
        idempotency_key: str, metodo_preparado_id: Optional[str] = None,
        off_session: bool = False, simular_requiere_accion: bool = False,
    ) -> IntencionPago:
        pi_id = f"pi_test_{secrets.token_hex(4)}"
        requiere = simular_requiere_accion or self.simular_requiere_accion
        if requiere:
            estado = "REQUIRES_ACTION"
        elif off_session:
            estado = "SUCCEEDED"
        else:
            estado = "REQUIRES_PAYMENT"

        inten = IntencionPago(
            id=pi_id,
            venta_id=recurso_id,
            monto_centavos=monto_centavos,
            moneda=moneda,
            estado=estado,
            client_secret=f"{pi_id}_secret_test",
        )
        self.intenciones[pi_id] = inten
        self.por_venta[recurso_id] = pi_id
        return inten

    async def confirmar_intencion(self, payment_intent_id: str) -> IntencionPago:
        if payment_intent_id not in self.intenciones:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Intención no encontrada")
        inten = self.intenciones[payment_intent_id]
        inten.estado = "SUCCEEDED"
        return inten

    async def crear_reembolso(
        self, payment_intent_id: str, centavos_usd: int, idempotency_key: Optional[str] = None,
    ) -> ReembolsoInfo:
        re_id = f"re_test_{secrets.token_hex(4)}"
        reemb = ReembolsoInfo(
            id=re_id,
            payment_intent_id=payment_intent_id,
            centavos_usd=centavos_usd,
            estado="succeeded",
        )
        self.reembolsos[re_id] = reemb
        return reemb

    # Helpers de prueba: transiciones controladas sin red.
    def marcar(self, pi_id: str, estado: str) -> None:
        if pi_id in self.intenciones:
            self.intenciones[pi_id].estado = estado


def verificar_firma_stripe(cuerpo_crudo: bytes, encabezado_firma: Optional[str], secreto: str) -> dict:
    """Verifica Stripe-Signature (t=...,v1=...) contra el cuerpo crudo.

    Lanza FirmaStripeInvalida si falta, expiró (>5 min) o no coincide.
    Retorna {'timestamp': int} para auditoría (sin datos sensibles).
    """
    if not encabezado_firma or not secreto:
        raise FirmaStripeInvalida("Falta firma o secreto de webhook")
    partes: dict[str, str] = {}
    for trozo in (encabezado_firma or "").split(","):
        if "=" in trozo:
            k, v = trozo.strip().split("=", 1)
            partes[k.strip()] = v.strip()
    t = partes.get("t", "")
    v1 = partes.get("v1", "")
    if not t or not v1:
        raise FirmaStripeInvalida("Formato de firma inválido")
    try:
        ts = int(t)
    except ValueError:
        raise FirmaStripeInvalida("Timestamp de firma inválido")
    if abs(time.time() - ts) > 300:
        raise FirmaStripeInvalida("Firma vencida")
    esperado = hmac.new(
        secreto.encode("utf-8"), f"{t}.".encode("utf-8") + cuerpo_crudo, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(esperado, v1):
        raise FirmaStripeInvalida("Firma del webhook no coincide")
    return {"timestamp": ts}


def firmar_prueba(cuerpo: bytes, secreto: str, ts: Optional[int] = None) -> str:
    """Solo pruebas: genera un encabezado Stripe-Signature válido."""
    marca = ts if ts is not None else int(time.time())
    firma = hmac.new(
        secreto.encode("utf-8"), f"{marca}.".encode("utf-8") + cuerpo, hashlib.sha256
    ).hexdigest()
    return f"t={marca},v1={firma}"


# Instancia conmutable: tests la reemplazan; producción usa el adaptador real.
_gateway_actual: Optional[StripeGateway] = None


def fijar_gateway(gateway: Optional[StripeGateway]) -> None:
    global _gateway_actual
    _gateway_actual = gateway


def es_clave_test_mode(clave: str) -> bool:
    """True solo para claves de Test Mode (sk_test_/rk_test_)."""
    c = (clave or "").strip()
    return c.startswith("sk_test_") or c.startswith("rk_test_")


def es_clave_live(clave: str) -> bool:
    c = (clave or "").strip()
    return c.startswith("sk_live_") or c.startswith("rk_live_")


def exigir_test_mode() -> None:
    """Rechaza claves live o fuera de Test Mode sin exponer la clave.

    Nunca imprime la clave ni su prefijo completo en errores o logs.
    """
    clave = settings.STRIPE_SECRET_KEY or ""
    if es_clave_live(clave):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "codigo": "STRIPE_MODO_NO_PERMITIDO",
                "mensaje": "Pasarela solo en Test Mode; clave live no permitida",
            },
        )
    if not es_clave_test_mode(clave):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "codigo": "STRIPE_MODO_NO_PERMITIDO",
                "mensaje": "Pasarela solo en Test Mode; configure una clave de prueba",
            },
        )


def obtener_gateway() -> StripeGateway:
    """503 tipado si Stripe está deshabilitado o sin claves (módulos sanos)."""
    if _gateway_actual is not None:
        return _gateway_actual
    if not settings.STRIPE_ENABLED or not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "codigo": "STRIPE_DESHABILITADO",
                "mensaje": "Pasarela en modo prueba no configurada. "
                "Configure STRIPE_SECRET_KEY y STRIPE_ENABLED=true en backend/.env",
            },
        )
    exigir_test_mode()
    return _StripeReal()


class _StripeReal(StripeGateway):
    """Adaptador productivo mínimo vía httpx (solo con claves del usuario)."""

    async def crear_o_reutilizar_intencion(
        self, venta_id, monto_centavos, moneda, idempotency_key, referencia_existente=None,
    ) -> IntencionPago:
        import httpx

        if referencia_existente:
            return await self.consultar_intencion(referencia_existente)
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                "https://api.stripe.com/v1/payment_intents",
                auth=(settings.STRIPE_SECRET_KEY, ""),
                headers={"Idempotency-Key": idempotency_key or secrets.token_hex(16)},
                data={
                    "amount": str(monto_centavos),
                    "currency": moneda,
                    "metadata[venta_id]": venta_id,
                },
            )
        if r.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"codigo": "STRIPE_RECHAZO", "mensaje": "La pasarela rechazó la intención"},
            )
        data: Any = r.json()
        return IntencionPago(
            id=data["id"], venta_id=venta_id, monto_centavos=int(data["amount"]),
            moneda=data.get("currency", moneda), estado="REQUIRES_PAYMENT",
            client_secret=data.get("client_secret"),
        )

    async def consultar_intencion(self, payment_intent_id: str) -> IntencionPago:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.get(
                f"https://api.stripe.com/v1/payment_intents/{payment_intent_id}",
                auth=(settings.STRIPE_SECRET_KEY, ""),
            )
        if r.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"codigo": "STRIPE_CONSULTA_FALLIDA", "mensaje": "No se pudo consultar la intención"},
            )
        data: Any = r.json()
        mapa = {
            "requires_payment_method": "REQUIRES_PAYMENT",
            "requires_action": "REQUIRES_ACTION",
            "succeeded": "SUCCEEDED",
            "canceled": "CANCELED",
        }
        estado = mapa.get(str(data.get("status", "")), "REQUIRES_PAYMENT")
        return IntencionPago(
            id=data["id"], venta_id=str(data.get("metadata", {}).get("venta_id", "")),
            monto_centavos=int(data.get("amount", 0)), moneda=str(data.get("currency", "usd")),
            estado=estado, client_secret=data.get("client_secret"),
        )

    async def crear_setup_intent(
        self, cliente_id: str, idempotency_key: Optional[str] = None,
    ) -> SetupIntentInfo:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                "https://api.stripe.com/v1/setup_intents",
                auth=(settings.STRIPE_SECRET_KEY, ""),
                headers={"Idempotency-Key": idempotency_key or secrets.token_hex(16)},
                data={"usage": "off_session", "metadata[cliente_id]": cliente_id},
            )
        if r.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"codigo": "STRIPE_RECHAZO", "mensaje": "La pasarela rechazó el setup intent"},
            )
        data = r.json()
        return SetupIntentInfo(
            id=data["id"],
            cliente_id=cliente_id,
            estado=data.get("status", "requires_payment_method"),
            client_secret=data.get("client_secret"),
        )

    async def crear_pago_conectado(
        self, recurso_id: str, monto_centavos: int, moneda: str,
        idempotency_key: str, metodo_preparado_id: Optional[str] = None,
        off_session: bool = False, simular_requiere_accion: bool = False,
    ) -> IntencionPago:
        import httpx

        post_data = {
            "amount": str(monto_centavos),
            "currency": moneda,
            "metadata[recurso_id]": recurso_id,
        }
        if off_session:
            post_data["off_session"] = "true"
            post_data["confirm"] = "true"
        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                "https://api.stripe.com/v1/payment_intents",
                auth=(settings.STRIPE_SECRET_KEY, ""),
                headers={"Idempotency-Key": idempotency_key or secrets.token_hex(16)},
                data=post_data,
            )
        if r.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"codigo": "STRIPE_RECHAZO", "mensaje": "La pasarela rechazó el pago conectado"},
            )
        data = r.json()
        st = data.get("status", "")
        estado = "SUCCEEDED" if st == "succeeded" else ("REQUIRES_ACTION" if st == "requires_action" else "REQUIRES_PAYMENT")
        return IntencionPago(
            id=data["id"], venta_id=recurso_id, monto_centavos=int(data["amount"]),
            moneda=data.get("currency", moneda), estado=estado, client_secret=data.get("client_secret"),
        )

    async def confirmar_intencion(self, payment_intent_id: str) -> IntencionPago:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                f"https://api.stripe.com/v1/payment_intents/{payment_intent_id}/confirm",
                auth=(settings.STRIPE_SECRET_KEY, ""),
            )
        if r.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"codigo": "STRIPE_CONFIRMACION_FALLIDA", "mensaje": "No se pudo confirmar la intención"},
            )
        data = r.json()
        return IntencionPago(
            id=data["id"], venta_id=str(data.get("metadata", {}).get("recurso_id", "")),
            monto_centavos=int(data.get("amount", 0)), moneda=str(data.get("currency", "usd")),
            estado="SUCCEEDED", client_secret=data.get("client_secret"),
        )

    async def crear_reembolso(
        self, payment_intent_id: str, centavos_usd: int, idempotency_key: Optional[str] = None,
    ) -> ReembolsoInfo:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as cli:
            r = await cli.post(
                "https://api.stripe.com/v1/refunds",
                auth=(settings.STRIPE_SECRET_KEY, ""),
                headers={"Idempotency-Key": idempotency_key or secrets.token_hex(16)},
                data={"payment_intent": payment_intent_id, "amount": str(centavos_usd)},
            )
        if r.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"codigo": "STRIPE_REEMBOLSO_FALLIDO", "mensaje": "No se pudo procesar el reembolso en Stripe"},
            )
        data = r.json()
        return ReembolsoInfo(
            id=data["id"], payment_intent_id=payment_intent_id,
            centavos_usd=int(data.get("amount", centavos_usd)), estado=data.get("status", "succeeded"),
        )
