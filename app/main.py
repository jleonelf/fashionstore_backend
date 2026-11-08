import sys
from pathlib import Path

# Permitir ejecucion tanto desde la raiz como desde dentro de /backend
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent.parent
if str(RAIZ_PROYECTO) not in sys.path:
    sys.path.insert(0, str(RAIZ_PROYECTO))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from backend.app.core.config import settings
from backend.app.api.v1.api import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.EXPIRACION_JOB_ACTIVO:
        from backend.app.core.tareas import iniciar_scheduler

        iniciar_scheduler(settings.EXPIRACION_JOB_MINUTOS)
    yield
    if settings.EXPIRACION_JOB_ACTIVO:
        from backend.app.core.tareas import detener_scheduler

        detener_scheduler()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API RESTful de FashionStore - Plataforma de Comercio Electrónico Omnicanal con Vestidor Virtual e IA",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Configuración CORS para Angular Web y Flutter Móvil
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.exception_handler(Exception)
async def error_interno_no_controlado(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    origin = request.headers.get("origin") or "*"
    headers = {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*",
    }
    return JSONResponse(
        status_code=500,
        content={"detail": f"Error interno: {type(exc).__name__}: {str(exc)}"},
        headers=headers,
    )

@app.get("/health", tags=["Salud"])
async def verificar_salud():
    return {
        "estado": "operativo",
        "servicio": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "zona_horaria_negocio": settings.BUSINESS_TIMEZONE,
    }

@app.get(f"{settings.API_V1_STR}/debug-db", tags=["Salud"])
async def debug_db():
    from backend.app.core.database import AsyncSessionLocal
    from sqlalchemy import text
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text(
                "SELECT conname, pg_get_constraintdef(c.oid) "
                "FROM pg_constraint c "
                "WHERE conrelid = 'inventario.movimientos_inventario'::regclass;"
            ))
            constraints = {row[0]: row[1] for row in res}
            return {
                "version": "debug-ciclo3-v4",
                "constraints": constraints,
            }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
