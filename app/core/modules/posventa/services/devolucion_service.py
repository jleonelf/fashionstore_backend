"""Controller DevolucionService / MermaService — CU12 (RF22)."""
import uuid
from decimal import Decimal
from typing import Tuple

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.idempotencia import hash_payload
from backend.app.core.permisos import es_admin, exigir_sucursal
from backend.app.core.reloj import RelojSistema
from backend.app.core.modules.ventas_pagos.models import DetalleVenta
from backend.app.core.modules.inventario.models import MovimientoInventario
from backend.app.core.modules.identidad_empresas.models import Usuario
from backend.app.core.modules.inventario.repositories.inventario_repository import InventarioRepository
from backend.app.core.modules.inventario.repositories.movimiento_repository import MovimientoRepository
from backend.app.core.modules.ventas_pagos.repositories.venta_repository import DetalleVentaRepository, VentaRepository
from backend.app.core.modules.catalogo.repositories.variante_repository import VarianteRepository
from backend.app.core.modules.posventa.schemas import (
    DevolucionCrearDTO,
    DevolucionDTO,
    MermaCrearDTO,
    MermaDTO,
)


class DevolucionService:
    def __init__(self, db: AsyncSession, reloj=None):
        self.db = db
        self.reloj = reloj or RelojSistema()
        self.detalle_repo = DetalleVentaRepository(db)
        self.venta_repo = VentaRepository(db)
        self.inventario_repo = InventarioRepository(db)
        self.movimiento_repo = MovimientoRepository(db)

    def _autorizar(self, usuario: Usuario, sucursal_id: uuid.UUID) -> None:
        rol = (usuario.rol.nombre if usuario.rol else "").upper()
        if rol == "ENCARGADO":
            exigir_sucursal(usuario, sucursal_id)
            return
        if es_admin(usuario):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Encargado o Administrador")

    @staticmethod
    def _a_dto(mov: MovimientoInventario, venta_id: uuid.UUID) -> DevolucionDTO:
        return DevolucionDTO(
            id=mov.id,
            detalle_venta_id=mov.referencia_id,
            venta_id=venta_id,
            variante_id=mov.variante_id,
            sucursal_id=mov.sucursal_destino_id,
            cantidad=mov.cantidad,
            costo_unitario=mov.costo_unitario,
            motivo=mov.observacion,
            responsable_id=mov.responsable_id,
            fecha_hora=mov.fecha_hora,
        )

    async def registrar(
        self, usuario: Usuario, dto: DevolucionCrearDTO, clave: uuid.UUID
    ) -> Tuple[DevolucionDTO, bool]:
        digest = hash_payload(dto.model_dump(mode="json"))
        try:
            previo = await self.movimiento_repo.buscarPorClaveIdempotencia(clave)
            if previo is not None:
                if (
                    previo.tipo != "DEVOLUCION"
                    or previo.referencia_tipo != "DETALLE_VENTA"
                    or previo.referencia_id != dto.detalle_venta_id
                    or previo.cantidad != dto.cantidad
                ):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency-Key ya usada con otra solicitud")
                venta_prev = None
                det_prev = await self.db.get(DetalleVenta, dto.detalle_venta_id)
                if det_prev is not None:
                    venta_prev = await self.venta_repo.buscarPorId(det_prev.venta_id)
                return self._a_dto(previo, venta_prev.id if venta_prev else None), False
            salida = await self._registrar_en_tx(usuario, dto, clave)
            await self.db.commit()
            return salida, True
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto concurrente de idempotencia")
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise

    async def _registrar_en_tx(
        self, usuario: Usuario, dto: DevolucionCrearDTO, clave: uuid.UUID
    ) -> DevolucionDTO:
        if dto.cantidad <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cantidad a devolver debe ser mayor a cero")
        detalle = await self.db.get(DetalleVenta, dto.detalle_venta_id)
        if detalle is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Detalle de venta no encontrado")
        venta = await self.venta_repo.buscarPorId(detalle.venta_id)
        if venta is None:  # pragma: no cover
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Venta no encontrada")
        self._autorizar(usuario, venta.sucursal_id)
        acumulado = await self.detalle_repo.cantidadDevueltaAcumulada(detalle.id)
        if acumulado + dto.cantidad > detalle.cantidad:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Excede lo vendido (vendido {detalle.cantidad}, ya devuelto {acumulado})",
            )
        filas = await self.inventario_repo.bloquearFilas([(venta.sucursal_id, detalle.variante_id)])
        fila = filas[(venta.sucursal_id, detalle.variante_id)]
        if fila is None:  # pragma: no cover
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sin registro de inventario en sucursal")
        fila.disponible += dto.cantidad
        await self.db.flush()
        mov = MovimientoInventario(
            variante_id=detalle.variante_id,
            sucursal_destino_id=venta.sucursal_id,
            responsable_id=usuario.id,
            tipo="DEVOLUCION",
            cantidad=dto.cantidad,
            costo_unitario=Decimal(str(detalle.costo_promedio or 0)),
            referencia_tipo="DETALLE_VENTA",
            referencia_id=detalle.id,
            linea_referencia_id=uuid.uuid4(),
            clave_idempotencia=clave,
            observacion=dto.motivo,
        )
        creado, _ = await self.movimiento_repo.registrarUnico(mov)
        total_vendido, total_devuelto = 0, 0
        for det in (await self.venta_repo.buscarPorId(venta.id)).detalles:
            total_vendido += det.cantidad
            total_devuelto += await self.detalle_repo.cantidadDevueltaAcumulada(det.id)
        if total_devuelto >= total_vendido and total_vendido > 0:
            venta.estado = "DEVUELTA"
        elif total_devuelto > 0 and venta.estado == "PAGADA":
            venta.estado = "PARCIALMENTE_DEVUELTA"
        await self.db.flush()
        return self._a_dto(creado, venta.id)


class MermaService:
    def __init__(self, db: AsyncSession, reloj=None):
        self.db = db
        self.reloj = reloj or RelojSistema()
        self.inventario_repo = InventarioRepository(db)
        self.movimiento_repo = MovimientoRepository(db)
        self.variante_repo = VarianteRepository(db)

    def _autorizar(self, usuario: Usuario, sucursal_id: uuid.UUID) -> None:
        rol = (usuario.rol.nombre if usuario.rol else "").upper()
        if rol == "ENCARGADO":
            exigir_sucursal(usuario, sucursal_id)
            return
        if es_admin(usuario):
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo Encargado o Administrador")

    @staticmethod
    def _a_dto(mov: MovimientoInventario) -> MermaDTO:
        return MermaDTO(
            id=mov.id, variante_id=mov.variante_id, sucursal_id=mov.sucursal_destino_id,
            cantidad=mov.cantidad, costo_unitario=mov.costo_unitario,
            causa=mov.observacion, responsable_id=mov.responsable_id, fecha_hora=mov.fecha_hora,
        )

    async def registrar(
        self, usuario: Usuario, dto: MermaCrearDTO, clave: uuid.UUID
    ) -> Tuple[MermaDTO, bool]:
        digest = hash_payload(dto.model_dump(mode="json"))
        try:
            previo = await self.movimiento_repo.buscarPorClaveIdempotencia(clave)
            if previo is not None:
                if (
                    previo.tipo != "MERMA"
                    or previo.variante_id != dto.variante_id
                    or previo.sucursal_destino_id != dto.sucursal_id
                    or previo.cantidad != dto.cantidad
                    or (previo.observacion or "") != (dto.causa or "")
                ):
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Idempotency-Key ya usada con otra solicitud")
                return self._a_dto(previo), False
            salida = await self._registrar_en_tx(usuario, dto, clave)
            await self.db.commit()
            return salida, True
        except IntegrityError:
            await self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Conflicto concurrente de idempotencia")
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception:
            await self.db.rollback()
            raise

    async def _registrar_en_tx(self, usuario: Usuario, dto: MermaCrearDTO, clave: uuid.UUID) -> MermaDTO:
        if dto.cantidad <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cantidad de merma debe ser mayor a cero")
        if not dto.causa or not dto.causa.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La merma exige causa documentada")
        self._autorizar(usuario, dto.sucursal_id)
        variante = await self.variante_repo.buscarPorId(dto.variante_id)
        if variante is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante no encontrada")
        responsable_id = dto.responsable_id or usuario.id
        responsable = await self.db.get(Usuario, responsable_id)
        if responsable is None or responsable.estado != "ACTIVO":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Responsable no encontrado o inactivo")
        filas = await self.inventario_repo.bloquearFilas([(dto.sucursal_id, dto.variante_id)])
        fila = filas[(dto.sucursal_id, dto.variante_id)]
        if fila is None or fila.disponible < dto.cantidad:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Sin stock disponible para registrar merma")
        fila.disponible -= dto.cantidad
        await self.db.flush()
        mov = MovimientoInventario(
            variante_id=dto.variante_id,
            sucursal_destino_id=dto.sucursal_id,
            responsable_id=responsable_id,
            tipo="MERMA",
            cantidad=dto.cantidad,
            costo_unitario=Decimal(str(variante.costo_promedio or 0)),
            referencia_tipo="MERMA",
            referencia_id=uuid.uuid4(),
            linea_referencia_id=None,
            clave_idempotencia=clave,
            observacion=dto.causa.strip(),
        )
        creado, _ = await self.movimiento_repo.registrarUnico(mov)
        return self._a_dto(creado)
