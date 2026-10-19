import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from backend.app.core.modules.catalogo.models import VarianteProducto
from backend.app.core.modules.catalogo.schemas import VarianteCrearDTO, VarianteDTO, VarianteActualizarDTO
from backend.app.core.modules.catalogo.repositories.variante_repository import VarianteRepository
from backend.app.core.modules.catalogo.repositories.producto_repository import ProductoRepository
from backend.app.core.modules.catalogo.repositories.maestro_repository import MaestroRepository

class VarianteService:
    """
    Controller VarianteService.crear() para CU05
    Presentación gestionarVariantes() -> Controller VarianteService.crear() -> Datos VarianteRepository.crear()
    UQ enforcement 409 Conflict si duplica producto+talla+color, sku único, codigo_barras único.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.variante_repo = VarianteRepository(db)
        self.producto_repo = ProductoRepository(db)
        self.maestro_repo = MaestroRepository(db)

    async def crear(self, dto: VarianteCrearDTO) -> VarianteDTO:
        producto = await self.producto_repo.buscarPorId(dto.producto_id)
        if not producto:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Producto no encontrado")
        if not producto.activo:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Producto inactivo, no se pueden crear variantes")

        talla = await self.maestro_repo.buscarTallaPorId(dto.talla_id)
        if not talla:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Talla no encontrada")
        if not talla.activo:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Talla inactiva")

        color = await self.maestro_repo.buscarColorPorId(dto.color_id)
        if not color:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Color no encontrado")
        if not color.activo:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Color inactivo")

        existente_sku = await self.variante_repo.buscarPorSku(dto.sku)
        if existente_sku:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una variante con SKU '{dto.sku}'")

        if dto.codigo_barras:
            existente_cb = await self.variante_repo.buscarPorCodigoBarras(dto.codigo_barras)
            if existente_cb:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una variante con código de barras '{dto.codigo_barras}'")

        existente_combo = await self.variante_repo.buscarPorProductoTallaColor(dto.producto_id, dto.talla_id, dto.color_id)
        if existente_combo:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe una variante para la combinación producto+talla+color")

        variante = VarianteProducto(
            producto_id=dto.producto_id,
            talla_id=dto.talla_id,
            color_id=dto.color_id,
            sku=dto.sku.strip(),
            codigo_barras=dto.codigo_barras.strip() if dto.codigo_barras else None,
            precio=dto.precio,
            peso_gramos=dto.peso_gramos,
            costo_promedio=0,
            costo_ultimo=0,
            recurso_prueba_virtual=dto.recurso_prueba_virtual,
            activa=dto.activa
        )
        try:
            await self.variante_repo.crear(variante)
            await self.db.commit()
            await self.db.refresh(variante)
        except IntegrityError as e:
            await self.db.rollback()
            msg = str(e.orig) if hasattr(e, 'orig') else str(e)
            if "uq_variante_prod_talla_color" in msg or "producto_id" in msg and "talla_id" in msg:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe una variante para la combinación producto+talla+color")
            if "sku" in msg.lower():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una variante con SKU '{dto.sku}'")
            if "codigo_barras" in msg.lower():
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una variante con código de barras '{dto.codigo_barras}'")
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto de unicidad: {msg}")
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al crear variante: {str(e)}")

        return VarianteDTO.model_validate(variante)

    async def listar(self, producto_id: Optional[uuid.UUID] = None, solo_activas: bool = False, limit: int = 50, offset: int = 0) -> List[VarianteDTO]:
        variantes = await self.variante_repo.listar(producto_id=producto_id, solo_activas=solo_activas, limit=limit, offset=offset)
        return [VarianteDTO.model_validate(v) for v in variantes]

    async def obtenerPorId(self, variante_id: uuid.UUID) -> VarianteDTO:
        variante = await self.variante_repo.buscarPorId(variante_id)
        if not variante:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante no encontrada")
        return VarianteDTO.model_validate(variante)

    async def actualizar(self, variante_id: uuid.UUID, dto: VarianteActualizarDTO) -> VarianteDTO:
        variante = await self.variante_repo.buscarPorId(variante_id)
        if not variante:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variante no encontrada")

        if "sku" in dto.model_fields_set and dto.sku is not None:
            nuevo_sku = dto.sku.strip()
            if nuevo_sku != variante.sku:
                existente = await self.variante_repo.buscarPorSku(nuevo_sku)
                if existente and existente.id != variante_id:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una variante con SKU '{nuevo_sku}'")
                variante.sku = nuevo_sku

        if "codigo_barras" in dto.model_fields_set:
            nuevo_cb = dto.codigo_barras.strip() if dto.codigo_barras and dto.codigo_barras.strip() else None
            if nuevo_cb != variante.codigo_barras:
                if nuevo_cb:
                    existente = await self.variante_repo.buscarPorCodigoBarras(nuevo_cb)
                    if existente and existente.id != variante_id:
                        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una variante con código de barras '{nuevo_cb}'")
                variante.codigo_barras = nuevo_cb

        if "precio" in dto.model_fields_set and dto.precio is not None:
            variante.precio = dto.precio

        if "peso_gramos" in dto.model_fields_set:
            variante.peso_gramos = dto.peso_gramos

        if "activa" in dto.model_fields_set and dto.activa is not None:
            variante.activa = dto.activa

        if "recurso_prueba_virtual" in dto.model_fields_set:
            variante.recurso_prueba_virtual = dto.recurso_prueba_virtual.strip() if dto.recurso_prueba_virtual and dto.recurso_prueba_virtual.strip() else None

        try:
            await self.variante_repo.actualizar(variante)
            await self.db.commit()
            await self.db.refresh(variante)
        except IntegrityError as e:
            await self.db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Conflicto de unicidad al actualizar: {str(e)}")
        except HTTPException:
            await self.db.rollback()
            raise
        return VarianteDTO.model_validate(variante)
