from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import AppError
from app.models.api import MovimientoCrear
from app.models.estado import Estado
from app.routers.api import router as api_router
from app.routers.sockets import router as socket_router
from app.services.demo_service import ControlGrua
from app.services.repository import Repository
from app.services.status_service import StatusService


def create_app(repository=None):
    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            await app.state.control.cerrar()

    app = FastAPI(
        title="Grúa IoT", description="Gestión MySQL y control de grúa por WebSocket",
        version="2.0.0", lifespan=lifespan,
    )
    repo = repository if repository is not None else Repository()
    app.state.control = ControlGrua(repo)
    app.state.status_service = StatusService(repo)

    @app.exception_handler(AppError)
    async def manejar_error(request: Request, error: AppError):
        return JSONResponse(status_code=error.status_code, content={"detail": error.detail})

    app.include_router(api_router)
    app.include_router(socket_router)

    @app.get("/status", tags=["Compatibilidad"])
    async def obtener_estado():
        return await app.state.control.db(app.state.status_service.obtener_estado)

    @app.post("/status", tags=["Compatibilidad"])
    async def cambiar_estado(datos: Estado):
        # codigo 12 requiere seleccionar una demo mediante la ruta nueva.
        if datos.status == 12:
            raise AppError(422, "Usa /vehiculos/{id}/movimientos con codigo 12 e id_demo")
        resultado = await app.state.control.movimiento(
            app.state.status_service.id_vehiculo, MovimientoCrear(codigo=datos.status)
        )
        return {"status": datos.status, "resultado": resultado}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
