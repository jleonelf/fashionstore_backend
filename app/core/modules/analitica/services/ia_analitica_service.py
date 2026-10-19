"""Service IA Analítica y Reportes — CU21 (reportes generativos) y CU25 (decisiones de inventario)."""
import time
import uuid
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.integraciones.ia_proveedor import proveedor_activo, rechazar_inyeccion
from backend.app.core.permisos import es_admin, rol_de
from backend.app.core.reloj import RelojSistema
from backend.app.core.modules.catalogo.models import VarianteProducto
from backend.app.core.modules.experiencia_cliente.models import SolicitudIA
from backend.app.core.modules.inventario.models import InventarioSucursal
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.analitica.schemas import (
    DecisionItemDTO,
    DecisionRespuestaDTO,
    ReporteRespuestaDTO,
)

LIMITE_AUDITORIA_TEXTO = 500


def _sanitizar(texto: str, maximo: int = LIMITE_AUDITORIA_TEXTO) -> str:
    return (texto or "").strip()[:maximo]


class IAAnaliticaService:
    FUNCIONES_SEGURAS = (
        "ventasPorSucursal",
        "inventarioPorSucursal",
        "ventasPorTemporada",
        "stockCritico",
        "topVendidos",
        "efectividadReservas",
        "rotacionPorTemporada",
    )

    def __init__(self, db: AsyncSession, reloj=None):
        self.db = db
        self.reloj = reloj or RelojSistema()
        self.proveedor = proveedor_activo()

    async def _auditar(
        self,
        usuario: Usuario,
        tipo: str,
        entrada: str,
        funcion: Optional[str],
        parametros: dict,
        respuesta: str,
        datos: dict,
        latencia_ms: int,
    ) -> None:
        self.db.add(
            SolicitudIA(
                usuario_id=usuario.id,
                cliente_id=usuario.id if rol_de(usuario) == "CLIENTE" else None,
                tipo=tipo,
                entrada=_sanitizar(entrada),
                funcion_usada=funcion,
                parametros=parametros or {},
                respuesta=_sanitizar(respuesta, 2000),
                datos=datos or {},
                proveedor=getattr(self.proveedor, "nombre", "DETERMINISTA"),
                latencia_ms=max(latencia_ms, 0),
            )
        )
        await self.db.flush()

    # ---------------- CU21 reportes generativos (solo lectura) ----------------
    def _elegir_funcion(self, consulta: str) -> tuple[str, dict]:
        bajo = (consulta or "").lower()
        menciona_inventario = any(p in bajo for p in ("inventario", "stock", "existencia"))
        menciona_sucursal = any(p in bajo for p in ("sucursal", "tienda", "local"))
        if menciona_inventario and menciona_sucursal:
            return "inventarioPorSucursal", {}
        if any(p in bajo for p in ("stock crítico", "stock critico", "inventario bajo", "agot")):
            return "stockCritico", {}
        if any(p in bajo for p in ("sucursal", "tienda", "local", "vendió menos", "vendio menos", "ventas por")):
            return "ventasPorSucursal", {}
        if "temporada" in bajo:
            return "ventasPorTemporada", {}
        if any(p in bajo for p in ("stock", "crítico", "critico", "agot", "inventario bajo")):
            return "stockCritico", {}
        if any(p in bajo for p in ("top", "más vend", "mas vend", "mejor vend")):
            return "topVendidos", {}
        if "reserva" in bajo:
            return "efectividadReservas", {}
        if any(p in bajo for p in ("rotaci", "lenta", "dead", "baja rot")):
            return "rotacionPorTemporada", {}
        return "ventasPorSucursal", {}

    async def generarReporte(self, usuario: Usuario, consulta: str) -> ReporteRespuestaDTO:
        rol = rol_de(usuario)
        if rol not in ("ADMINISTRADOR", "ENCARGADO") and not es_admin(usuario):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Administración")
        motivo = rechazar_inyeccion(consulta)
        if motivo:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=motivo)
        inicio = time.monotonic()
        funcion, params = self._elegir_funcion(consulta)
        assert funcion in self.FUNCIONES_SEGURAS
        datos = await self._ejecutar_funcion(funcion, params)
        narrativa = await self.proveedor.narrar(f"Reporte {funcion}", datos)
        latencia = int((time.monotonic() - inicio) * 1000)
        try:
            await self._auditar(
                usuario, "REPORTE", consulta, funcion, params, narrativa, datos, latencia,
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
        return ReporteRespuestaDTO(
            funcion_usada=funcion,
            parametros=params,
            datos=datos,
            narrativa=narrativa,
            proveedor=getattr(self.proveedor, "nombre", "DETERMINISTA"),
        )

    async def _ejecutar_funcion(self, funcion: str, params: dict) -> dict:
        from backend.app.core.modules.ventas_pagos.models import DetalleVenta, Venta
        from backend.app.core.modules.organizacion.models import Sucursal

        if funcion == "ventasPorSucursal":
            q = (
                select(Sucursal.nombre, func.count(Venta.id), func.coalesce(func.sum(Venta.total), 0))
                .join(Venta, Venta.sucursal_id == Sucursal.id)
                .where(Venta.estado == "PAGADA")
                .group_by(Sucursal.nombre)
                .order_by(Sucursal.nombre)
            )
            filas = (await self.db.execute(q)).all()
            return {
                "por_sucursal": [
                    {"sucursal": n, "ventas": int(c), "ingresos": str(t)} for n, c, t in filas
                ],
                "total": len(filas),
            }
        if funcion == "inventarioPorSucursal":
            q = (
                select(
                    Sucursal.nombre,
                    func.count(InventarioSucursal.variante_id),
                    func.coalesce(func.sum(InventarioSucursal.disponible), 0),
                    func.coalesce(func.sum(InventarioSucursal.reservado), 0),
                    func.coalesce(func.sum(InventarioSucursal.en_transito), 0),
                )
                .join(InventarioSucursal, InventarioSucursal.sucursal_id == Sucursal.id)
                .where(Sucursal.activa.is_(True))
                .group_by(Sucursal.nombre)
                .order_by(Sucursal.nombre)
            )
            filas = (await self.db.execute(q)).all()
            return {
                "inventario_por_sucursal": [
                    {
                        "sucursal": nombre,
                        "variantes": int(variantes or 0),
                        "disponible": int(disponible or 0),
                        "reservado": int(reservado or 0),
                        "en_transito": int(en_transito or 0),
                    }
                    for nombre, variantes, disponible, reservado, en_transito in filas
                ],
                "total": len(filas),
            }
        if funcion == "ventasPorTemporada":
            from backend.app.core.modules.catalogo.models import Temporada

            q = select(Temporada.nombre).order_by(Temporada.nombre)
            temps = [r[0] for r in (await self.db.execute(q)).all()]
            return {"temporadas": temps, "total": len(temps)}
        if funcion == "stockCritico":
            q = (
                select(VarianteProducto.sku, InventarioSucursal.disponible)
                .join(InventarioSucursal, InventarioSucursal.variante_id == VarianteProducto.id)
                .where(InventarioSucursal.disponible <= 5)
                .order_by(InventarioSucursal.disponible)
                .limit(50)
            )
            filas = (await self.db.execute(q)).all()
            return {"criticos": [{"sku": s, "disponible": int(d)} for s, d in filas], "total": len(filas)}
        if funcion == "topVendidos":
            q = (
                select(VarianteProducto.sku, func.sum(DetalleVenta.cantidad).label("uds"))
                .join(DetalleVenta, DetalleVenta.variante_id == VarianteProducto.id)
                .join(Venta, Venta.id == DetalleVenta.venta_id)
                .where(Venta.estado == "PAGADA")
                .group_by(VarianteProducto.sku)
                .order_by(func.sum(DetalleVenta.cantidad).desc())
                .limit(10)
            )
            filas = (await self.db.execute(q)).all()
            return {"top": [{"sku": s, "unidades": int(u)} for s, u in filas]}
        if funcion == "efectividadReservas":
            from backend.app.core.modules.reservas_traslados.models import Reserva

            tot = int((await self.db.execute(select(func.count()).select_from(Reserva))).scalar() or 0)
            comp = int((await self.db.execute(
                select(func.count()).select_from(Reserva).where(Reserva.estado == "COMPLETADA")
            )).scalar() or 0)
            return {
                "total": tot,
                "completadas": comp,
                "conversion": round(comp / tot, 4) if tot else 0.0,
            }
        if funcion == "rotacionPorTemporada":
            return await self._rotacion(30)
        return {}

    async def _rotacion(self, dias: int) -> dict:
        from datetime import timedelta as _td
        from backend.app.core.modules.ventas_pagos.models import DetalleVenta, Venta

        desde = self.reloj.ahora() - _td(days=dias)
        q = (
            select(DetalleVenta.variante_id, func.sum(DetalleVenta.cantidad))
            .join(Venta, Venta.id == DetalleVenta.venta_id)
            .where(Venta.estado == "PAGADA", Venta.creada_en >= desde)
            .group_by(DetalleVenta.variante_id)
        )
        ventas = {str(v): int(c) for v, c in (await self.db.execute(q)).all()}
        inv = await self.db.execute(
            select(
                InventarioSucursal.variante_id,
                func.sum(InventarioSucursal.disponible + InventarioSucursal.reservado),
            ).group_by(InventarioSucursal.variante_id)
        )
        filas = []
        for vid, stock in inv.all():
            filas.append(
                {
                    "variante_id": str(vid),
                    "stock": int(stock or 0),
                    "ventas": int(ventas.get(str(vid), 0)),
                }
            )
        return {"ventana_dias": dias, "filas": filas}

    # ---------------- CU25 decisiones de inventario (solo recomienda) ----------------
    async def decisionesInventario(
        self,
        usuario: Usuario,
        dias_ventana: int = 30,
        umbral_rotacion: int = 2,
    ) -> DecisionRespuestaDTO:
        rol = rol_de(usuario)
        if rol not in ("ADMINISTRADOR", "ENCARGADO") and not es_admin(usuario):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Administración")
        inicio = time.monotonic()
        datos = await self._rotacion(dias_ventana)
        items: List[DecisionItemDTO] = []
        for fila in datos["filas"]:
            vid = uuid.UUID(fila["variante_id"])
            variante = await self.db.get(VarianteProducto, vid)
            if variante is None:
                continue
            ventas = int(fila["ventas"])
            stock = int(fila["stock"])
            if stock <= 0:
                continue
            if ventas <= umbral_rotacion and stock >= 5:
                accion, detalle = "PROMOCION", (
                    f"Baja rotación ({ventas} vendidas en {dias_ventana} días, stock {stock}): "
                    "sugerir promoción o liquidación"
                )
            elif ventas <= umbral_rotacion:
                accion, detalle = "TRASLADO", (
                    f"Sin rotación local ({ventas} en {dias_ventana} días): evaluar traslado"
                )
            elif stock < ventas / max(dias_ventana, 1) * 14:
                promedio = ventas / max(dias_ventana, 1)
                repo = int(round(promedio * 14))
                accion, detalle = "REPOSICION", (
                    f"Reposición estimada: promedio {promedio:.2f}/día × 14 días de proveedor ≈ {repo} un."
                )
                items.append(
                    DecisionItemDTO(
                        variante_id=vid,
                        sku=variante.sku,
                        accion=accion,
                        detalle=detalle,
                        stock_total=stock,
                        ventas_periodo=ventas,
                        reposicion_sugerida=repo,
                    )
                )
                continue
            else:
                accion, detalle = "MANTENER", (
                    f"Rotación sana ({ventas} en {dias_ventana} días, stock {stock})"
                )
            items.append(
                DecisionItemDTO(
                    variante_id=vid,
                    sku=variante.sku,
                    accion=accion,
                    detalle=detalle,
                    stock_total=stock,
                    ventas_periodo=ventas,
                )
            )
        latencia = int((time.monotonic() - inicio) * 1000)
        try:
            await self._auditar(
                usuario,
                "DECISION_INVENTARIO",
                f"ventana={dias_ventana} umbral={umbral_rotacion}",
                "rotacionPorTemporada",
                {"dias": dias_ventana},
                f"{len(items)} decisiones sugeridas (ningún cambio ejecutado)",
                {"total": len(items)},
                latencia,
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
        return DecisionRespuestaDTO(
            items=items,
            proveedor=getattr(self.proveedor, "nombre", "DETERMINISTA"),
        )
