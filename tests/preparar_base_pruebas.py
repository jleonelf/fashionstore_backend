"""Prepara la base de pruebas del backend (Ciclo 2).

Crea ``fashionstore_test`` (o la base ``*_test`` indicada), aplica el esquema
completo desde los modelos y carga una semilla mínima: roles, ciudad,
una sucursal y el admin de pruebas (``TEST_ADMIN_EMAIL`` /
``TEST_ADMIN_PASSWORD``). La suite crea y limpia el resto de sus datos.

Uso (no toca ``backend/.env`` ni ``fashionstore_db``)::

    cd backend
    $env:POSTGRES_DB = "fashionstore_test"
    venv\\Scripts\\python.exe tests/preparar_base_pruebas.py
    venv\\Scripts\\alembic upgrade head
    $env:TEST_ADMIN_EMAIL = "admin@fashionstore.com"
    $env:TEST_ADMIN_PASSWORD = "Fashion123!"
    venv\\Scripts\\python.exe -m pytest tests/ -q

Se niega a operar si la base no termina en ``_test``.
"""

import asyncio
import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import app  # noqa: F401,E402  configura alias backend.*
from sqlalchemy import select  # noqa: E402


def nombre_base_objetivo() -> str:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        return urlsplit(url.split("?")[0]).path.rstrip("/").rsplit("/", 1)[-1]
    return os.getenv("TEST_POSTGRES_DB") or os.getenv(
        "POSTGRES_DB", "fashionstore_db"
    )


def _env(nombre: str, defecto: str = "") -> str:
    """Lee variable de entorno con respaldo en ``backend/.env`` (sin
    imprimir secretos)."""
    valor = os.getenv(nombre)
    if valor:
        return valor
    try:
        ruta = BACKEND_ROOT / ".env"
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea.startswith(nombre + "="):
                return linea.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return defecto


def _conexion_params(base: str) -> dict:
    url = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        u = urlsplit(url)
        return {
            "host": u.hostname or "127.0.0.1",
            "port": u.port or 5432,
            "user": u.username or "postgres",
            "password": u.password
            or os.getenv("TEST_POSTGRES_PASSWORD")
            or os.getenv("POSTGRES_PASSWORD", "postgres"),
            "database": base,
        }
    return {
        "host": os.getenv("TEST_POSTGRES_SERVER")
        or _env("POSTGRES_SERVER", "127.0.0.1"),
        "port": int(
            os.getenv("TEST_POSTGRES_PORT")
            or _env("POSTGRES_PORT", "5432")
        ),
        "user": os.getenv("TEST_POSTGRES_USER")
        or _env("POSTGRES_USER", "postgres"),
        "password": os.getenv("TEST_POSTGRES_PASSWORD")
        or _env("POSTGRES_PASSWORD", "postgres"),
        "database": base,
        "ssl": False,
    }


async def crear_base_si_falta(nombre: str) -> bool:
    import asyncpg

    params = _conexion_params("postgres")
    conn = await asyncpg.connect(**params)
    try:
        existe = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", nombre
        )
        if existe:
            print(f"[=] La base '{nombre}' ya existe.")
            return False
        await conn.execute(f'CREATE DATABASE "{nombre}"')
        print(f"[+] Base '{nombre}' creada.")
        return True
    finally:
        await conn.close()


ESQUEMAS = (
    "seguridad",
    "organizacion",
    "catalogo",
    "inventario",
    "comercial",
    "inteligencia",
)


async def crear_esquemas() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.app.core.config import settings

    engine = create_async_engine(settings.async_database_url)
    try:
        async with engine.begin() as conn:
            for esquema in ESQUEMAS:
                await conn.execute(
                    text(f"CREATE SCHEMA IF NOT EXISTS {esquema}")
                )
        print("[+] Esquemas verificados.")
    finally:
        await engine.dispose()


def aplicar_migraciones() -> None:
    """Ejecuta ``alembic upgrade head`` (crea tipos ENUM y tablas Ciclo 2).

    Las revisiones son idempotentes (guardas IF NOT EXISTS).
    """
    import subprocess

    exe = Path(sys.prefix) / "Scripts" / "alembic"
    print("[*] Aplicando migraciones (alembic upgrade head)...")
    subprocess.run([str(exe), "upgrade", "head"], cwd=BACKEND_ROOT, check=True)
    print("[+] Migraciones aplicadas.")


# Tablas del Ciclo 2 (las crea la migración 0001 con sus tipos ENUM).
# Se excluyen del primer create_all porque la migración asume que las
# tablas del Ciclo 1 ya existen (FK hacia seguridad.clientes, etc.).
# Las tablas del Ciclo 3 las crea la migración 0004; también se excluyen
# de esta primera fase para que migración y modelos no compitan.
TABLAS_CICLO2 = frozenset(
    {
        "reservas",
        "detalles_reserva",
        "traslados",
        "detalles_traslado",
        "ventas",
        "detalles_venta",
        "pagos",
    }
)
TABLAS_CICLO3 = frozenset(
    {
        "carritos",
        "detalles_carrito",
        "pedidos_entrega",
        "promociones",
        "promocion_variante",
        "historial_navegacion",
        "solicitudes_ia",
        "registros_idempotencia",
    }
)


async def liberar_indices_de_migracion() -> None:
    """Elimina índices que el modelo declara con el mismo nombre pero con
    definición más débil que la migración.

    ``uq_movimientos_efecto_logico`` existe en los modelos como índice UNIQUE
    plano (NULL distintos entre sí) mientras la migración 0001 lo define con
    COALESCE (NULL comparables). Como la migración usa
    ``CREATE UNIQUE INDEX IF NOT EXISTS``, hay que soltar el plano antes para
    que se cree la versión con COALESCE, idéntica a ``fashionstore_db``.

    Solo se suelta cuando la definición actual NO es la de la migración:
    en re-ejecuciones alembic ya está en head y no recrearía nada.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.app.core.config import settings

    engine = create_async_engine(settings.async_database_url)
    try:
        async with engine.begin() as conn:
            definicion = (
                await conn.execute(
                    text(
                        "SELECT indexdef FROM pg_indexes "
                        "WHERE schemaname = 'inventario' "
                        "AND indexname = 'uq_movimientos_efecto_logico'"
                    )
                )
            ).scalar_one_or_none()
            if definicion is None:
                print("[=] Índice uq_movimientos_efecto_logico ausente; "
                      "lo creará la migración.")
            elif "COALESCE" in definicion.upper():
                print("[=] Índice uq_movimientos_efecto_logico ya es el de "
                      "la migración; se conserva.")
            else:
                await conn.execute(
                    text(
                        "DROP INDEX inventario.uq_movimientos_efecto_logico"
                    )
                )
                print("[+] Índice plano liberado para la migración.")
    finally:
        await engine.dispose()


async def verificar_indice_efecto_logico() -> None:
    """Garantiza el índice UNIQUE con COALESCE de la migración 0001.

    Repara bases donde el índice falte (p. ej. tras una limpieza) aunque
    alembic ya esté en head. DDL idéntico al de la migración.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.app.core.config import settings

    engine = create_async_engine(settings.async_database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_movimientos_efecto_logico "
                    "ON inventario.movimientos_inventario ("
                    "referencia_tipo, referencia_id, tipo, variante_id, "
                    "COALESCE(sucursal_origen_id, "
                    "'00000000-0000-0000-0000-000000000000'::uuid), "
                    "COALESCE(sucursal_destino_id, "
                    "'00000000-0000-0000-0000-000000000000'::uuid), "
                    "COALESCE(linea_referencia_id, "
                    "'00000000-0000-0000-0000-000000000000'::uuid)) "
                    "WHERE referencia_tipo IS NOT NULL "
                    "AND referencia_id IS NOT NULL"
                )
            )
        print("[+] Índice uq_movimientos_efecto_logico verificado.")
    finally:
        await engine.dispose()


async def aplicar_esquema_ciclo1() -> None:
    """Crea las tablas previas al Ciclo 2 (la migración 0001 las asume)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.app.core.config import settings
    from backend.app.core.database import Base
    import backend.app.db.modelos  # noqa: F401  registra metadata completa

    tablas = [
        t
        for nombre, t in Base.metadata.tables.items()
        if nombre.rsplit(".", 1)[-1] not in TABLAS_CICLO2
        and nombre.rsplit(".", 1)[-1] not in TABLAS_CICLO3
    ]
    engine = create_async_engine(settings.async_database_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, tables=tablas)
        print("[+] Esquema Ciclo 1 aplicado desde los modelos.")
    finally:
        await engine.dispose()


async def aplicar_esquema() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    from backend.app.core.config import settings
    from backend.app.core.database import Base
    import backend.app.db.modelos  # noqa: F401  registra metadata completa

    engine = create_async_engine(settings.async_database_url)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[+] Esquema aplicado desde los modelos.")
    finally:
        await engine.dispose()


async def semilla_minima() -> None:
    from backend.app.core.database import AsyncSessionLocal
    from backend.app.core.seguridad import generar_contrasenia_hash
    from backend.app.core.modules.catalogo.models import (
        Categoria,
        Color,
        Proveedor,
        Talla,
    )
    from backend.app.core.modules.organizacion.models import Ciudad, Sucursal
    from backend.app.core.modules.identidad_empresas.models import Rol, Usuario

    email_admin = os.getenv("TEST_ADMIN_EMAIL", "admin@fashionstore.com")
    clave_admin = os.getenv("TEST_ADMIN_PASSWORD", "Fashion123!")

    async with AsyncSessionLocal() as db:
        async with db.begin():
            roles = {}
            for nombre in (
                "ADMINISTRADOR",
                "ENCARGADO",
                "CAJERO",
                "PROVEEDOR",
                "CLIENTE",
            ):
                existente = (
                    await db.execute(select(Rol).where(Rol.nombre == nombre))
                ).scalars().first()
                if existente is None:
                    existente = Rol(
                        id=uuid.uuid4(),
                        nombre=nombre,
                        descripcion=f"Rol {nombre} (base de pruebas)",
                        activo=True,
                    )
                    db.add(existente)
                    print(f"  + Rol {nombre}")
                roles[nombre] = existente

            ciudad = (
                await db.execute(
                    select(Ciudad).where(
                        Ciudad.nombre == "Santa Cruz de la Sierra"
                    )
                )
            ).scalars().first()
            if ciudad is None:
                ciudad = Ciudad(
                    id=uuid.uuid4(),
                    nombre="Santa Cruz de la Sierra",
                    activo=True,
                )
                db.add(ciudad)
                print("  + Ciudad Santa Cruz de la Sierra")

            sucursal = (
                await db.execute(select(Sucursal).limit(1))
            ).scalars().first()
            if sucursal is None:
                db.add(
                    Sucursal(
                        id=uuid.uuid4(),
                        ciudad_id=ciudad.id,
                        nombre="Sucursal Pruebas",
                        direccion="Av. Pruebas 123",
                        telefono="+591 70000000",
                        numero_anillo=1,
                        tarifa_base_delivery=Decimal("12"),
                        incremento_anillo_delivery=Decimal("3"),
                        anillo_minimo_delivery=1,
                        anillo_maximo_delivery=8,
                        delivery_activo=True,
                        activa=True,
                        adelanto_activo=False,
                        modalidad_adelanto=None,
                        valor_adelanto=Decimal("0"),
                    )
                )
                print("  + Sucursal Pruebas")

            admin = (
                await db.execute(
                    select(Usuario).where(
                        Usuario.correo_electronico == email_admin
                    )
                )
            ).scalars().first()
            if admin is None:
                db.add(
                    Usuario(
                        id=uuid.uuid4(),
                        rol_id=roles["ADMINISTRADOR"].id,
                        nombres="Administrador",
                        apellidos="Pruebas",
                        correo_electronico=email_admin,
                        contrasenia_hash=generar_contrasenia_hash(clave_admin),
                        telefono="+591 70000000",
                        estado="ACTIVO",
                    )
                )
                print(f"  + Admin {email_admin}")
            else:
                print(f"[=] Admin {email_admin} ya existe.")

            # Maestros mínimos de catálogo (algunas pruebas CU04 los asumen
            # existentes y crean el resto de sus datos por sí mismas).
            talla = (
                await db.execute(select(Talla).limit(1))
            ).scalars().first()
            if talla is None:
                db.add(Talla(nombre="M", orden=3, activo=True))
                print("  + Talla M")
            color = (
                await db.execute(select(Color).limit(1))
            ).scalars().first()
            if color is None:
                db.add(
                    Color(nombre="Negro", codigo_hex="#000000", activo=True)
                )
                print("  + Color Negro")
            categoria = (
                await db.execute(select(Categoria).limit(1))
            ).scalars().first()
            if categoria is None:
                db.add(Categoria(nombre="General", activo=True))
                print("  + Categoria General")
            proveedor = (
                await db.execute(select(Proveedor).limit(1))
            ).scalars().first()
            if proveedor is None:
                db.add(
                    Proveedor(
                        razon_social="Proveedor Pruebas",
                        nit="000000000",
                    )
                )
                print("  + Proveedor Pruebas")
    print("[+] Semilla mínima lista.")


async def main() -> None:
    nombre = nombre_base_objetivo()
    if not nombre.endswith("_test"):
        raise RuntimeError(
            f"Rechazado: '{nombre}' no termina en '_test'. Configure "
            "POSTGRES_DB=fashionstore_test (ver tests/BASE_DE_PRUEBAS.md)."
        )
    await crear_base_si_falta(nombre)
    await crear_esquemas()
    await aplicar_esquema_ciclo1()
    await liberar_indices_de_migracion()
    aplicar_migraciones()
    await verificar_indice_efecto_logico()
    await aplicar_esquema()
    await semilla_minima()
    print(f"[OK] Base '{nombre}' lista para pytest.")


if __name__ == "__main__":
    asyncio.run(main())
