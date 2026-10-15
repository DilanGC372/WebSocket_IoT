
from fastapi import WebSocket
class WebSocketManager: 
    def __init__(self):
        self.clientes = []
 
    async def conectar(self, websocket: WebSocket):

        await websocket.accept()

        self.clientes.append(websocket)


    def desconectar(self, websocket: WebSocket):

        if websocket in self.clientes:

            self.clientes.remove(websocket)


    async def enviar_a_todos(self, mensaje):

        desconectados = []

        for cliente in self.clientes:

            try:

                await cliente.send_json(mensaje)

            except Exception:

                desconectados.append(cliente)

        for cliente in desconectados:

            self.desconectar(cliente)