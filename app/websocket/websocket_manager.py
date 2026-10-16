import asyncio
from collections import defaultdict

from app.errors import AppError


class WebSocketManager:
    """Una conexion de dispositivo por grua; observadores separados."""
    def __init__(self):
        self.dispositivos = {}
        self.observadores = defaultdict(set)
        self.legacy = defaultdict(set)
        self.envios = {}

    def conectado(self, vehiculo):
        return vehiculo in self.dispositivos

    async def enviar(self, socket, mensaje):
        lock = self.envios.setdefault(socket, asyncio.Lock())
        async with lock:
            await asyncio.wait_for(socket.send_json(mensaje), timeout=3)

    async def conectar_dispositivo(self, vehiculo, socket):
        if vehiculo in self.dispositivos:
            await socket.close(code=1008, reason="Ya hay un dispositivo conectado")
            return False
        # Reservar antes del primer await evita dos conexiones simultaneas.
        self.dispositivos[vehiculo] = socket
        try:
            await socket.accept()
        except BaseException:
            self.dispositivos.pop(vehiculo, None)
            raise
        return True

    async def orden(self, vehiculo, mensaje):
        socket = self.dispositivos.get(vehiculo)
        if socket is None:
            raise AppError(409, "La grua no esta conectada")
        try:
            await self.enviar(socket, mensaje)
        except Exception as error:
            try:
                await socket.close(code=1011)
            except Exception:
                pass
            raise AppError(503, "La orden se registro, pero fallo el envio a la grua") from error

    async def notificar(self, vehiculo, mensaje, legacy=False):
        grupo = self.legacy if legacy else self.observadores
        async def enviar_uno(socket):
            try:
                await self.enviar(socket, mensaje)
            except Exception:
                grupo[vehiculo].discard(socket)
                self.envios.pop(socket, None)
        await asyncio.gather(*(enviar_uno(s) for s in tuple(grupo[vehiculo])))

    def quitar(self, socket):
        self.envios.pop(socket, None)
        for grupo in (self.observadores, self.legacy):
            for sockets in grupo.values():
                sockets.discard(socket)
