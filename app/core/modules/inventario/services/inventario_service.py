import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.modules.inventario.repositories.inventario_repository import InventarioRepository
from backend.app.core.modules.inventario.repositories.movimiento_repository import MovimientoRepository
from backend.app.core.modules.catalogo.repositories.variante_repository import VarianteRepository
from backend.app.core.reloj import a_hora_bolivia, entrada_local_a_utc

class InventarioService:
    """
    Controller InventarioService para CU06 (RF08) y CU07 (RF21, RF22, RF26)
    Presentación consultarDisponibilidad() -> disponibilidadPorSucursal()
    Presentación consultarKardex() -> kardexPorVariante()
    Presentación consultarExistencias() -> existenciasPorSucursal()
    Presentación consultarValorizacion() -> valorizacion()
    Solo lectura + exposición de movimientos ya creados por CU04.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.inventario_repo = InventarioRepository(db)
        self.movimiento_repo = MovimientoRepository(db)
        self.variante_repo = VarianteRepository(db)

    # ---------- CU06 ----------

    async def disponibilidadPorSucursal(self, variante_id: uuid.UUID) -> List[Dict[str, Any]]:
        variante = await self.variante_repo.buscarPorId(variante_id)
        if not variante:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante no encontrada")
        disponibilidad = await self.inventario_repo.disponibilidadPorSucursal(variante_id)
        return disponibilidad

    async def consultarDisponibilidad(self, variante_id: uuid.UUID) -> List[Dict[str, Any]]:
        return await self.disponibilidadPorSucursal(variante_id)

    async def porVariante(self, variante_id: uuid.UUID) -> List[Dict[str, Any]]:
        return await self.disponibilidadPorSucursal(variante_id)

    # ---------- CU07 - Kardex ----------

    async def kardexPorVariante(
        self,
        variante_id: Optional[uuid.UUID] = None,
        sucursal_id: Optional[uuid.UUID] = None,
        tipo: Optional[str] = None,
        desde: Optional[datetime] = None,
        hasta: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        if variante_id is not None:
            variante = await self.variante_repo.buscarPorId(variante_id)
            if not variante:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante no encontrada")
        desde = entrada_local_a_utc(desde) if desde is not None else None
        hasta = entrada_local_a_utc(hasta) if hasta is not None else None
        movimientos = await self.movimiento_repo.listar(
            variante_id=variante_id,
            sucursal_id=sucursal_id,
            tipo=tipo,
            desde=desde,
            hasta=hasta,
            limit=limit,
            offset=offset,
        )
        out = []
        for m in movimientos:
            out.append({
                "id": str(m.id),
                "variante_id": str(m.variante_id),
                "sucursal_origen_id": str(m.sucursal_origen_id) if m.sucursal_origen_id else None,
                "sucursal_destino_id": str(m.sucursal_destino_id) if m.sucursal_destino_id else None,
                "responsable_id": str(m.responsable_id) if m.responsable_id else None,
                "tipo": m.tipo,
                "cantidad": m.cantidad,
                "costo_unitario": float(m.costo_unitario) if m.costo_unitario is not None else 0.0,
                "referencia_tipo": m.referencia_tipo,
                "referencia_id": str(m.referencia_id) if m.referencia_id else None,
                "fecha_hora": a_hora_bolivia(m.fecha_hora).isoformat() if m.fecha_hora else None,
                "observacion": m.observacion,
            })
        return out

    async def consultarKardex(
        self,
        variante_id: uuid.UUID,
        sucursal_id: Optional[uuid.UUID] = None,
        tipo: Optional[str] = None,
        desde: Optional[datetime] = None,
        hasta: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        return await self.kardexPorVariante(variante_id, sucursal_id, tipo, desde, hasta)

    async def kardexPorId(self, movimiento_id: uuid.UUID) -> Dict[str, Any]:
        mov = await self.movimiento_repo.buscarPorId(movimiento_id)
        if not mov:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Movimiento no encontrado")
        return {
            "id": str(mov.id),
            "variante_id": str(mov.variante_id),
            "sucursal_origen_id": str(mov.sucursal_origen_id) if mov.sucursal_origen_id else None,
            "sucursal_destino_id": str(mov.sucursal_destino_id) if mov.sucursal_destino_id else None,
            "responsable_id": str(mov.responsable_id) if mov.responsable_id else None,
            "tipo": mov.tipo,
            "cantidad": mov.cantidad,
            "costo_unitario": float(mov.costo_unitario) if mov.costo_unitario is not None else 0.0,
            "referencia_tipo": mov.referencia_tipo,
            "referencia_id": str(mov.referencia_id) if mov.referencia_id else None,
            "fecha_hora": a_hora_bolivia(mov.fecha_hora).isoformat() if mov.fecha_hora else None,
            "observacion": mov.observacion,
        }

    # ---------- CU07 - Existencias ----------

    async def existenciasPorSucursal(self, sucursal_id: uuid.UUID) -> List[Dict[str, Any]]:
        return await self.inventario_repo.existenciasEnriquecidas(sucursal_id=sucursal_id)

    async def existenciasPorVariante(self, variante_id: uuid.UUID) -> List[Dict[str, Any]]:
        variante = await self.variante_repo.buscarPorId(variante_id)
        if not variante:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante no encontrada")
        return await self.inventario_repo.porVarianteEnriquecido(variante_id)

    async def consultarExistencias(self, sucursal_id: Optional[uuid.UUID] = None) -> List[Dict[str, Any]]:
        if sucursal_id:
            return await self.existenciasPorSucursal(sucursal_id)
        return await self.inventario_repo.existenciasEnriquecidas(sucursal_id=None)

    # ---------- CU07 - Valorización ----------

    async def valorizacion(self, sucursal_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        if sucursal_id:
            por_sucursal = await self.inventario_repo.valorizacionPorSucursal(sucursal_id=sucursal_id)
            total_val = sum(s["valorizacion"] for s in por_sucursal)
            total_unidades = sum(s["total_unidades"] for s in por_sucursal)
            return {
                "por_sucursal": por_sucursal,
                "global": {
                    "total_unidades": total_unidades,
                    "valorizacion": round(total_val, 2),
                    "sucursales": len(por_sucursal),
                },
                "filtro_sucursal_id": str(sucursal_id),
            }
        return await self.inventario_repo.valorizacionGlobal()

    async def consultarValorizacion(self, sucursal_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
        return await self.valorizacion(sucursal_id)
