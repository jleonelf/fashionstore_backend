import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.app.core.modules.identidad_empresas.models import Usuario, Empleado
from backend.app.core.modules.organizacion.models import Sucursal
from backend.app.core.modules.identidad_empresas.schemas import UsuarioCrearDTO, UsuarioListadoDTO
from backend.app.core.modules.identidad_empresas.repositories.usuario_repository import UsuarioRepository
from backend.app.core.modules.identidad_empresas.repositories.rol_repository import RolRepository
from backend.app.core.modules.organizacion.repositories.sucursal_repository import SucursalRepository
from backend.app.core.seguridad import generar_contrasenia_hash


class UsuarioService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.usuario_repo = UsuarioRepository(db)
        self.rol_repo = RolRepository(db)
        self.sucursal_repo = SucursalRepository(db)

    def _requiere_sucursal(self, rol_nombre: str) -> bool:
        return rol_nombre.upper() in ("ENCARGADO", "CAJERO")

    async def crear(self, dto: UsuarioCrearDTO) -> UsuarioListadoDTO:
        # 1. Validar correo no duplicado
        existente = await self.usuario_repo.buscarPorCorreo(dto.correo_electronico)
        if existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El correo electrónico ya se encuentra registrado para otro usuario"
            )

        # 2. Validar que el rol exista
        rol = await self.rol_repo.buscarPorId(dto.rol_id)
        if not rol:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El rol especificado no existe en el sistema"
            )

        # 2b. Validar sucursal si rol requiere
        if self._requiere_sucursal(rol.nombre):
            if not dto.sucursal_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"El rol {rol.nombre} requiere asignar una sucursal (sucursal_id)"
                )
            suc = await self.sucursal_repo.buscarPorId(dto.sucursal_id)
            if not suc:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La sucursal especificada no existe")
        else:
            # Para ADMIN/CLIENTE/PROVEEDOR ignorar sucursal si viene
            if dto.sucursal_id:
                suc_check = await self.sucursal_repo.buscarPorId(dto.sucursal_id)
                if not suc_check:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="La sucursal especificada no existe")

        # 3. Hashear contraseña y crear usuario
        contrasenia_hash = generar_contrasenia_hash(dto.contrasenia)
        nuevo_usuario = Usuario(
            rol_id=dto.rol_id,
            nombres=dto.nombres.strip(),
            apellidos=dto.apellidos.strip(),
            correo_electronico=dto.correo_electronico.strip().lower(),
            contrasenia_hash=contrasenia_hash,
            telefono=dto.telefono.strip() if dto.telefono else None,
            estado="ACTIVO"
        )
        await self.usuario_repo.crear(nuevo_usuario)
        await self.db.flush()

        # 3b. Crear registro empleado si aplica
        sucursal_nombre = None
        cargo_val = dto.cargo.strip() if dto.cargo else None
        if dto.sucursal_id:
            if not cargo_val and self._requiere_sucursal(rol.nombre):
                cargo_val = "Encargado de Sucursal" if rol.nombre.upper() == "ENCARGADO" else "Cajero"
            empleado = Empleado(
                usuario_id=nuevo_usuario.id,
                sucursal_id=dto.sucursal_id,
                cargo=cargo_val or rol.nombre,
                activo=True
            )
            self.db.add(empleado)
            await self.db.flush()
            q = await self.db.execute(select(Sucursal).where(Sucursal.id == dto.sucursal_id))
            suc_obj = q.scalars().first()
            sucursal_nombre = suc_obj.nombre if suc_obj else None

        await self.db.commit()
        await self.db.refresh(nuevo_usuario)
        # recargar empleado
        result = await self.db.execute(
            select(Usuario).options(selectinload(Usuario.rol), selectinload(Usuario.empleado)).where(Usuario.id == nuevo_usuario.id)
        )
        usuario_full = result.scalars().first() or nuevo_usuario

        return UsuarioListadoDTO(
            id=usuario_full.id,
            rol_id=usuario_full.rol_id,
            rol_nombre=rol.nombre,
            nombres=usuario_full.nombres,
            apellidos=usuario_full.apellidos,
            nombre_completo=usuario_full.nombre_completo,
            correo_electronico=usuario_full.correo_electronico,
            telefono=usuario_full.telefono,
            estado=usuario_full.estado,
            creado_en=usuario_full.creado_en,
            actualizado_en=usuario_full.actualizado_en,
            sucursal_id=usuario_full.empleado.sucursal_id if usuario_full.empleado else None,
            sucursal_nombre=sucursal_nombre,
            cargo=usuario_full.empleado.cargo if usuario_full.empleado else None,
        )

    async def listar(self, rol_id: Optional[uuid.UUID] = None, estado: Optional[str] = None) -> List[UsuarioListadoDTO]:
        usuarios = await self.usuario_repo.listar(rol_id=rol_id, estado=estado)
        # resolver nombres de sucursal en batch
        suc_ids = {u.empleado.sucursal_id for u in usuarios if u.empleado and u.empleado.sucursal_id}
        suc_map = {}
        if suc_ids:
            q = await self.db.execute(select(Sucursal).where(Sucursal.id.in_(suc_ids)))
            for s in q.scalars().all():
                suc_map[s.id] = s.nombre
        return [
            UsuarioListadoDTO(
                id=u.id,
                rol_id=u.rol_id,
                rol_nombre=u.rol.nombre if u.rol else "SIN ROL",
                nombres=u.nombres,
                apellidos=u.apellidos,
                nombre_completo=u.nombre_completo,
                correo_electronico=u.correo_electronico,
                telefono=u.telefono,
                estado=u.estado,
                creado_en=u.creado_en,
                actualizado_en=u.actualizado_en,
                sucursal_id=u.empleado.sucursal_id if u.empleado else None,
                sucursal_nombre=suc_map.get(u.empleado.sucursal_id) if u.empleado else None,
                cargo=u.empleado.cargo if u.empleado else None,
            )
            for u in usuarios
        ]

    async def asignarRol(self, usuario_id: uuid.UUID, nuevo_rol_id: uuid.UUID) -> UsuarioListadoDTO:
        usuario = await self.usuario_repo.buscarPorId(usuario_id)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        rol = await self.rol_repo.buscarPorId(nuevo_rol_id)
        if not rol:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="El rol especificado no existe"
            )

        usuario_actualizado = await self.usuario_repo.asignarRol(usuario_id, nuevo_rol_id)
        await self.db.commit()
        # recargar con empleado
        usuario_actualizado = await self.usuario_repo.buscarPorId(usuario_id)
        emp = usuario_actualizado.empleado if usuario_actualizado else None
        suc_nombre = None
        if emp and emp.sucursal_id:
            q = await self.db.execute(select(Sucursal).where(Sucursal.id == emp.sucursal_id))
            s = q.scalars().first()
            suc_nombre = s.nombre if s else None

        return UsuarioListadoDTO(
            id=usuario_actualizado.id,
            rol_id=usuario_actualizado.rol_id,
            rol_nombre=rol.nombre,
            nombres=usuario_actualizado.nombres,
            apellidos=usuario_actualizado.apellidos,
            nombre_completo=usuario_actualizado.nombre_completo,
            correo_electronico=usuario_actualizado.correo_electronico,
            telefono=usuario_actualizado.telefono,
            estado=usuario_actualizado.estado,
            creado_en=usuario_actualizado.creado_en,
            actualizado_en=usuario_actualizado.actualizado_en,
            sucursal_id=emp.sucursal_id if emp else None,
            sucursal_nombre=suc_nombre,
            cargo=emp.cargo if emp else None,
        )

    async def actualizarEstado(self, usuario_id: uuid.UUID, nuevo_estado: str) -> UsuarioListadoDTO:
        usuario = await self.usuario_repo.buscarPorId(usuario_id)
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        usuario_actualizado = await self.usuario_repo.actualizarEstado(usuario_id, nuevo_estado)
        await self.db.commit()
        usuario_actualizado = await self.usuario_repo.buscarPorId(usuario_id)
        emp = usuario_actualizado.empleado if usuario_actualizado else None
        suc_nombre = None
        if emp and emp.sucursal_id:
            q = await self.db.execute(select(Sucursal).where(Sucursal.id == emp.sucursal_id))
            s = q.scalars().first()
            suc_nombre = s.nombre if s else None

        return UsuarioListadoDTO(
            id=usuario_actualizado.id,
            rol_id=usuario_actualizado.rol_id,
            rol_nombre=usuario_actualizado.rol.nombre if usuario_actualizado.rol else "SIN ROL",
            nombres=usuario_actualizado.nombres,
            apellidos=usuario_actualizado.apellidos,
            nombre_completo=usuario_actualizado.nombre_completo,
            correo_electronico=usuario_actualizado.correo_electronico,
            telefono=usuario_actualizado.telefono,
            estado=usuario_actualizado.estado,
            creado_en=usuario_actualizado.creado_en,
            actualizado_en=usuario_actualizado.actualizado_en,
            sucursal_id=emp.sucursal_id if emp else None,
            sucursal_nombre=suc_nombre,
            cargo=emp.cargo if emp else None,
        )

    async def desactivar(self, usuario_id: uuid.UUID) -> UsuarioListadoDTO:
        return await self.actualizarEstado(usuario_id, "INACTIVO")
