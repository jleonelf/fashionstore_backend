from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.modules.identidad_empresas.models import Usuario, Cliente
from backend.app.core.modules.identidad_empresas.schemas import RegistroClienteDTO, ClientePerfilDTO
from backend.app.core.modules.identidad_empresas.repositories.usuario_repository import UsuarioRepository
from backend.app.core.modules.identidad_empresas.repositories.cliente_repository import ClienteRepository
from backend.app.core.modules.identidad_empresas.repositories.rol_repository import RolRepository
from backend.app.core.seguridad import generar_contrasenia_hash


class ClienteService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.usuario_repo = UsuarioRepository(db)
        self.cliente_repo = ClienteRepository(db)
        self.rol_repo = RolRepository(db)

    async def registrar(self, dto: RegistroClienteDTO) -> ClientePerfilDTO:
        # 1. Validar correo no duplicado
        usuario_existente = await self.usuario_repo.buscarPorCorreo(dto.correo_electronico)
        if usuario_existente:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El correo electrónico ya se encuentra registrado en la plataforma"
            )

        # 2. Obtener rol de Cliente (crearlo si no existe en la inicialización)
        rol_cliente = await self.rol_repo.buscarPorNombre("CLIENTE")
        if not rol_cliente:
            rol_cliente = await self.rol_repo.buscarPorNombre("Cliente")
        if not rol_cliente:
            rol_cliente = await self.rol_repo.crear(
                nombre="CLIENTE",
                descripcion="Rol asignado automáticamente a los clientes registrados"
            )

        # 3. Hashear contraseña
        contrasenia_hash = generar_contrasenia_hash(dto.contrasenia)

        # 4. Crear entidad Usuario
        nuevo_usuario = Usuario(
            rol_id=rol_cliente.id,
            nombres=dto.nombres.strip(),
            apellidos=dto.apellidos.strip(),
            correo_electronico=dto.correo_electronico.strip().lower(),
            contrasenia_hash=contrasenia_hash,
            telefono=dto.telefono.strip() if dto.telefono else None,
            estado="ACTIVO"
        )
        await self.usuario_repo.crear(nuevo_usuario)

        # 5. Crear entidad Cliente
        nuevo_cliente = Cliente(
            usuario_id=nuevo_usuario.id,
            direccion_referencia=dto.direccion_referencia.strip() if dto.direccion_referencia else None,
            fecha_nacimiento=dto.fecha_nacimiento,
            preferencias=dto.preferencias or {}
        )
        await self.cliente_repo.crear(nuevo_cliente)

        await self.db.commit()
        await self.db.refresh(nuevo_usuario)

        return ClientePerfilDTO(
            id=nuevo_cliente.usuario_id,
            usuario_id=nuevo_usuario.id,
            nombres=nuevo_usuario.nombres,
            apellidos=nuevo_usuario.apellidos,
            nombre_completo=nuevo_usuario.nombre_completo,
            correo_electronico=nuevo_usuario.correo_electronico,
            telefono=nuevo_usuario.telefono,
            rol=rol_cliente.nombre,
            estado=nuevo_usuario.estado,
            direccion_referencia=nuevo_cliente.direccion_referencia,
            fecha_nacimiento=nuevo_cliente.fecha_nacimiento,
            preferencias=nuevo_cliente.preferencias,
            creado_en=nuevo_usuario.creado_en
        )
