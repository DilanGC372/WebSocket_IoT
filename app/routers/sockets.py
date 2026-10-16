import json

from anyio import CancelScope
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.errors import AppError
from app.models.api import Confirmacion, ControlDemo

router = APIRouter()


async def error_socket(c, socket, error):
    await c.hub.enviar(socket, {"evento": "error", "detalle": error.detail, "codigo": error.status_code})


@router.websocket("/ws/vehiculos/{id}")
async def dispositivo(socket: WebSocket, id: int):
    c = socket.app.state.control
    aceptado = False
    try:
        if id <= 0:
            await socket.close(code=1008)
            return
        async with c.locks[id]:
            await c.db(c.repo.vehiculo, id, True)
            c.libre(id)
            aceptado = await c.hub.conectar_dispositivo(id, socket)
            if not aceptado:
                return
            await c.db(c.repo.conexion, id, True)
            await c.hub.enviar(socket, {"evento": "conectado", "id_vehiculo": id})
            # Nunca reproducir el ultimo movimiento al reconectar.
            await c._enviar(id, 9, "CONEXION")
        while True:
            try:
                datos = Confirmacion.model_validate(await socket.receive_json())
                if datos.id_orden not in c.ordenes[id]:
                    raise AppError(422, "La confirmacion no corresponde a una orden de esta conexion")
                await c.hub.notificar(id, {**datos.model_dump(), "id_vehiculo": id,
                                          "codigo": c.ordenes[id][datos.id_orden]})
                if datos.resultado in ("ejecutado", "error"):
                    c.ordenes[id].pop(datos.id_orden, None)
            except (ValidationError, json.JSONDecodeError, KeyError):
                await error_socket(c, socket, AppError(422, "Confirmacion invalida"))
            except AppError as error:
                await error_socket(c, socket, error)
    except WebSocketDisconnect:
        pass
    except AppError as error:
        if aceptado:
            await error_socket(c, socket, error)
        await socket.close(code=1008 if error.status_code < 500 else 1011)
    finally:
        if aceptado:
            with CancelScope(shield=True):
                await c.desconectar(id, socket)
        c.hub.quitar(socket)


@router.websocket("/ws/vehiculos/{id}/demos")
async def demos(socket: WebSocket, id: int):
    c = socket.app.state.control
    aceptado = False
    try:
        if id <= 0:
            await socket.close(code=1008)
            return
        await c.db(c.repo.vehiculo, id)
        await socket.accept()
        aceptado = True
        c.hub.observadores[id].add(socket)
        actual = c.demos.get(id)
        await c.hub.enviar(socket, {"evento": "estado_demo", "id_demo": actual.id_demo if actual else None,
                                   "conectado": c.hub.conectado(id)})
        while True:
            try:
                datos = ControlDemo.model_validate(await socket.receive_json())
                if datos.accion == "iniciar":
                    await c.iniciar(id, datos.id_demo, propietario=socket)
                else:
                    resultado = await c.cancelar(id)
                    await c.hub.enviar(socket, resultado)
            except (ValidationError, json.JSONDecodeError, KeyError):
                await error_socket(c, socket, AppError(422, "Usa iniciar con id_demo o cancelar sin id_demo"))
            except AppError as error:
                await error_socket(c, socket, error)
    except WebSocketDisconnect:
        pass
    except AppError as error:
        if aceptado:
            await error_socket(c, socket, error)
        await socket.close(code=1008 if error.status_code < 500 else 1011)
    finally:
        c.hub.quitar(socket)
        actual = c.demos.get(id)
        if actual is not None and actual.propietario is socket:
            with CancelScope(shield=True):
                await c.cancelar(id, "controlador_desconectado")


@router.websocket("/ws")
async def observador_legacy(socket: WebSocket):
    c = socket.app.state.control
    servicio = socket.app.state.status_service
    id = servicio.id_vehiculo
    try:
        estado = await c.db(servicio.obtener_estado)
        await socket.accept()
        c.hub.legacy[id].add(socket)
        await c.hub.enviar(socket, estado)
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        pass
    except AppError:
        await socket.close(code=1011)
    finally:
        c.hub.quitar(socket)
