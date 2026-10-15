from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app.models.estado import Estado

from app.services.status_service import StatusService

from app.websocket.websocket_manager import WebSocketManager


app = FastAPI(title="Servidor IoT", description="API HTTP y WebSocket para práctica IoT", version="1.0")

status_service = StatusService()

websocket_manager = WebSocketManager()


@app.get("/status")

def obtener_estado():

    return status_service.obtener_estado()


@app.post("/status")

async def cambiar_estado(estado: Estado):

    nuevo_estado = status_service.guardar_estado(estado.status)

    await websocket_manager.enviar_a_todos(nuevo_estado)

    return nuevo_estado


@app.websocket("/ws")

async def websocket_endpoint(websocket: WebSocket):

    await websocket_manager.conectar(websocket)

    await websocket.send_json(status_service.obtener_estado())

    try:

        while True:

            await websocket.receive_text()

    except WebSocketDisconnect:

        websocket_manager.desconectar(websocket)


if __name__ == "__main__":

    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)