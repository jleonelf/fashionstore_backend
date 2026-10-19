import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.modules.organizacion.models import Sucursal
from backend.app.core.modules.organizacion.schemas import (
    SucursalCrearDTO, SucursalDTO, ConfigurarTarifasDeliveryDTO, ConfigurarAdelantoDTO,
)
from backend.app.core.modules.organizacion.repositories.sucursal_repository import SucursalRepository
from backend.app.core.modules.organizacion.repositories.ciudad_repository import CiudadRepository


class SucursalService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.sucursal_repo = SucursalRepository(db)
        self.ciudad_repo = CiudadRepository(db)

    async def crear(self, dto: SucursalCrearDTO) -> SucursalDTO:
        # 1. Validar que la ciudad exista
        ciudad = await self.ciudad_repo.buscarPorId(dto.ciudad_id)
        if not ciudad:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="La ciudad especificada no existe"
            )

        # 2. Validar que no exista sucursal con el mismo nombre en la misma ciudad
        existente = await self.sucursal_repo.buscarPorCiudadYNombre(dto.ciudad_id, dto.nombre)
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una sucursal con el nombre '{dto.nombre.strip()}' en {ciudad.nombre}"
            )

        nueva_sucursal = Sucursal(
            ciudad_id=dto.ciudad_id,
            nombre=dto.nombre.strip(),
            direccion=dto.direccion.strip(),
            telefono=dto.telefono.strip() if dto.telefono else None,
            numero_anillo=dto.numero_anillo,
            tarifa_base_delivery=dto.tarifa_base_delivery,
            incremento_anillo_delivery=dto.incremento_anillo_delivery,
            anillo_minimo_delivery=dto.anillo_minimo_delivery,
            anillo_maximo_delivery=dto.anillo_maximo_delivery,
            delivery_activo=dto.delivery_activo,
            activa=True
        )
        await self.sucursal_repo.crear(nueva_sucursal)
        await self.db.commit()
        await self.db.refresh(nueva_sucursal)

        return SucursalDTO(
            id=nueva_sucursal.id,
            ciudad_id=nueva_sucursal.ciudad_id,
            ciudad_nombre=ciudad.nombre,
            nombre=nueva_sucursal.nombre,
            direccion=nueva_sucursal.direccion,
            telefono=nueva_sucursal.telefono,
            numero_anillo=nueva_sucursal.numero_anillo,
            tarifa_base_delivery=nueva_sucursal.tarifa_base_delivery,
            incremento_anillo_delivery=nueva_sucursal.incremento_anillo_delivery,
            anillo_minimo_delivery=nueva_sucursal.anillo_minimo_delivery,
            anillo_maximo_delivery=nueva_sucursal.anillo_maximo_delivery,
            delivery_activo=nueva_sucursal.delivery_activo,
            activa=nueva_sucursal.activa,
            adelanto_activo=nueva_sucursal.adelanto_activo,
            modalidad_adelanto=nueva_sucursal.modalidad_adelanto,
            valor_adelanto=nueva_sucursal.valor_adelanto
        )

    async def listar(self, ciudad_id: Optional[uuid.UUID] = None, solo_activas: bool = True) -> List[SucursalDTO]:
        sucursales = await self.sucursal_repo.listar(ciudad_id=ciudad_id, solo_activas=solo_activas)
        return [
            SucursalDTO(
                id=s.id,
                ciudad_id=s.ciudad_id,
                ciudad_nombre=s.ciudad.nombre if s.ciudad else None,
                nombre=s.nombre,
                direccion=s.direccion,
                telefono=s.telefono,
                numero_anillo=s.numero_anillo,
                tarifa_base_delivery=s.tarifa_base_delivery,
                incremento_anillo_delivery=s.incremento_anillo_delivery,
                anillo_minimo_delivery=s.anillo_minimo_delivery,
                anillo_maximo_delivery=s.anillo_maximo_delivery,
                delivery_activo=s.delivery_activo,
                activa=s.activa
            )
            for s in sucursales
        ]

    async def obtenerPorId(self, sucursal_id: uuid.UUID) -> SucursalDTO:
        s = await self.sucursal_repo.buscarPorId(sucursal_id)
        if not s:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sucursal no encontrada"
            )
        return SucursalDTO(
            id=s.id,
            ciudad_id=s.ciudad_id,
            ciudad_nombre=s.ciudad.nombre if s.ciudad else None,
            nombre=s.nombre,
            direccion=s.direccion,
            telefono=s.telefono,
            numero_anillo=s.numero_anillo,
            tarifa_base_delivery=s.tarifa_base_delivery,
            incremento_anillo_delivery=s.incremento_anillo_delivery,
            anillo_minimo_delivery=s.anillo_minimo_delivery,
            anillo_maximo_delivery=s.anillo_maximo_delivery,
            delivery_activo=s.delivery_activo,
            activa=s.activa,
            adelanto_activo=s.adelanto_activo,
            modalidad_adelanto=s.modalidad_adelanto,
            valor_adelanto=s.valor_adelanto
        )

    async def actualizarTarifas(self, sucursal_id: uuid.UUID, dto: ConfigurarTarifasDeliveryDTO) -> SucursalDTO:
        s = await self.sucursal_repo.buscarPorId(sucursal_id)
        if not s:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sucursal no encontrada"
            )

        actualizada = await self.sucursal_repo.actualizarTarifas(
            sucursal_id=sucursal_id,
            tarifa_base_delivery=dto.tarifa_base_delivery,
            incremento_anillo_delivery=dto.incremento_anillo_delivery,
            anillo_minimo_delivery=dto.anillo_minimo_delivery,
            anillo_maximo_delivery=dto.anillo_maximo_delivery,
            delivery_activo=dto.delivery_activo
        )
        await self.db.commit()

        return SucursalDTO(
            id=actualizada.id,
            ciudad_id=actualizada.ciudad_id,
            ciudad_nombre=actualizada.ciudad.nombre if actualizada.ciudad else None,
            nombre=actualizada.nombre,
            direccion=actualizada.direccion,
            telefono=actualizada.telefono,
            numero_anillo=actualizada.numero_anillo,
            tarifa_base_delivery=actualizada.tarifa_base_delivery,
            incremento_anillo_delivery=actualizada.incremento_anillo_delivery,
            anillo_minimo_delivery=actualizada.anillo_minimo_delivery,
            anillo_maximo_delivery=actualizada.anillo_maximo_delivery,
            delivery_activo=actualizada.delivery_activo,
            activa=actualizada.activa,
            adelanto_activo=actualizada.adelanto_activo,
            modalidad_adelanto=actualizada.modalidad_adelanto,
            valor_adelanto=actualizada.valor_adelanto
        )

    async def actualizarAdelanto(self, sucursal_id: uuid.UUID, dto: ConfigurarAdelantoDTO) -> SucursalDTO:
        """Configura la politica de adelanto por sucursal (decision 13, RN-03)."""
        s = await self.sucursal_repo.buscarPorId(sucursal_id)
        if not s:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sucursal no encontrada")
        modalidad = (dto.modalidad_adelanto or "").upper() if dto.modalidad_adelanto else None
        if dto.adelanto_activo:
            if modalidad not in ("MONTO_FIJO", "PORCENTAJE"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="modalidad_adelanto debe ser MONTO_FIJO o PORCENTAJE cuando el adelanto esta activo",
                )
            if dto.valor_adelanto is None or dto.valor_adelanto <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="valor_adelanto debe ser positivo cuando el adelanto esta activo",
                )
            if modalidad == "PORCENTAJE" and dto.valor_adelanto > 100:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="valor_adelanto no puede superar 100 en modalidad PORCENTAJE",
                )
        actualizada = await self.sucursal_repo.actualizarAdelanto(
            sucursal_id=sucursal_id,
            adelanto_activo=dto.adelanto_activo,
            modalidad_adelanto=modalidad,
            valor_adelanto=dto.valor_adelanto,
        )
        await self.db.commit()
        return SucursalDTO(
            id=actualizada.id,
            ciudad_id=actualizada.ciudad_id,
            ciudad_nombre=actualizada.ciudad.nombre if actualizada.ciudad else None,
            nombre=actualizada.nombre,
            direccion=actualizada.direccion,
            telefono=actualizada.telefono,
            numero_anillo=actualizada.numero_anillo,
            tarifa_base_delivery=actualizada.tarifa_base_delivery,
            incremento_anillo_delivery=actualizada.incremento_anillo_delivery,
            anillo_minimo_delivery=actualizada.anillo_minimo_delivery,
            anillo_maximo_delivery=actualizada.anillo_maximo_delivery,
            delivery_activo=actualizada.delivery_activo,
            activa=actualizada.activa,
            adelanto_activo=actualizada.adelanto_activo,
            modalidad_adelanto=actualizada.modalidad_adelanto,
            valor_adelanto=actualizada.valor_adelanto
        )
