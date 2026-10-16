import asyncio
import logging
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field
from uuid import uuid4

from starlette.concurrency import run_in_threadpool

from app.errors import AppError
from app.websocket.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


@dataclass(eq=False)
class Ejecucion:
    id_demo: int
    propietario: object | None = None
    cancelar: asyncio.Event = field(default_factory=asyncio.Event)
    tarea: asyncio.Task | None = None
    motivo: str = "cancelada"


class ControlGrua:
    def __init__(self, repository):
        self.repo = repository
        self.hub = WebSocketManager()
        self.locks = defaultdict(asyncio.Lock)
        self.demos = {}
        self.ordenes = defaultdict(OrderedDict)
        self.cerrando = False

    async def db(self, funcion, *args):
        return await run_in_threadpool(funcion, *args)

    def libre(self, vehiculo):
        if vehiculo in self.demos:
            raise AppError(409, "Hay una demo activa; usa DETENER o cancelar")

    async def _enviar(self, vehiculo, codigo, origen, duracion_ms=None):
        if not self.hub.conectado(vehiculo):
            raise AppError(409, "La grua no esta conectada")
        comando = await self.db(self.repo.registrar, vehiculo, codigo, True, origen)
        mensaje = {
            "evento": "orden", "id_orden": str(uuid4()),
            "id_vehiculo": vehiculo, "codigo": codigo, "status": codigo,
            "comando": comando["nombre"], "origen": origen,
        }
        if duracion_ms is not None:
            mensaje["duracion_ms"] = duracion_ms
        pendientes = self.ordenes[vehiculo]
        pendientes[mensaje["id_orden"]] = codigo
        if len(pendientes) > 256:
            pendientes.popitem(last=False)
        await self.hub.orden(vehiculo, mensaje)
        await self.hub.notificar(vehiculo, {"status": codigo}, legacy=True)
        return {**mensaje, "envio": "enviado", "ejecucion_confirmada": False}

    async def movimiento(self, vehiculo, datos):
        if datos.codigo == 12:
            return await self.iniciar(vehiculo, datos.id_demo)
        async with self.locks[vehiculo]:
            ejecucion = self.demos.get(vehiculo)
            if ejecucion:
                if datos.codigo != 9:
                    self.libre(vehiculo)
                ejecucion.cancelar.set()
            else:
                return await self._enviar(vehiculo, datos.codigo, datos.origen)
        # Esperar fuera del lock: la demo enviara DETENER antes de terminar.
        await asyncio.shield(ejecucion.tarea)
        return {"codigo": 9, "demo_cancelada": True, "ejecucion_confirmada": False}

    async def iniciar(self, vehiculo, demo, propietario=None):
        async with self.locks[vehiculo]:
            if self.cerrando:
                raise AppError(503, "El servidor se esta cerrando")
            self.libre(vehiculo)
            if not self.hub.conectado(vehiculo):
                raise AppError(409, "La grua no esta conectada")
            pasos = await self.db(self.repo.secuencia, vehiculo, demo)
            # El codigo 12 es una solicitud del servidor, no un paso del firmware.
            await self.db(self.repo.registrar, vehiculo, 12, True, "DEMO")
            ejecucion = Ejecucion(demo, propietario=propietario)
            self.demos[vehiculo] = ejecucion
            ejecucion.tarea = asyncio.create_task(self._ejecutar(vehiculo, ejecucion, pasos))
            await self.hub.notificar(vehiculo, {"evento": "demo_iniciada", "id_demo": demo, "pasos": len(pasos)})
            return {"evento": "demo_iniciada", "id_demo": demo, "pasos": len(pasos)}

    async def _esperar(self, ejecucion, ms):
        try:
            await asyncio.wait_for(ejecucion.cancelar.wait(), timeout=ms / 1000)
            return True
        except TimeoutError:
            return ejecucion.cancelar.is_set()

    async def _ejecutar(self, vehiculo, ejecucion, pasos):
        error = None
        try:
            for paso in pasos:
                async with self.locks[vehiculo]:
                    if ejecucion.cancelar.is_set():
                        break
                    orden = await self._enviar(vehiculo, paso["codigo"], "DEMO", paso["duracion_ms"])
                await self.hub.notificar(vehiculo, {
                    "evento": "paso_enviado", "id_demo": ejecucion.id_demo,
                    "orden": paso["orden"], "codigo": paso["codigo"], "id_orden": orden["id_orden"],
                })
                if await self._esperar(ejecucion, paso["duracion_ms"]):
                    break
                if 1 <= paso["codigo"] <= 8:
                    async with self.locks[vehiculo]:
                        if ejecucion.cancelar.is_set():
                            break
                        await self._enviar(vehiculo, 9, "DEMO")
                if await self._esperar(ejecucion, paso["pausa_ms"]):
                    break
        except AppError as exc:
            error = exc.detail
        except Exception:
            logger.exception("Fallo en demo de vehiculo %s", vehiculo)
            error = "Fallo inesperado en la demo"
        finally:
            async with self.locks[vehiculo]:
                detenido = False
                if self.hub.conectado(vehiculo):
                    try:
                        await self._enviar(vehiculo, 9, "DEMO")
                        detenido = True
                    except AppError as exc:
                        error = error or exc.detail
                        # Si MySQL falla, intentar detener sin afirmar que fue registrado.
                        try:
                            await self.hub.orden(vehiculo, {"evento": "orden", "codigo": 9, "status": 9,
                                                          "origen": "EMERGENCIA", "registrado": False})
                            detenido = True
                        except AppError:
                            pass
                evento = "demo_error" if error else ("demo_cancelada" if ejecucion.cancelar.is_set() else "demo_finalizada")
                await self.hub.notificar(vehiculo, {
                    "evento": evento, "id_demo": ejecucion.id_demo,
                    "motivo": error or (ejecucion.motivo if ejecucion.cancelar.is_set() else "secuencia_enviada"),
                    "detener_enviado": detenido, "ejecucion_confirmada": False,
                })
                if self.demos.get(vehiculo) is ejecucion:
                    self.demos.pop(vehiculo, None)

    async def cancelar(self, vehiculo, motivo="cancelada"):
        async with self.locks[vehiculo]:
            ejecucion = self.demos.get(vehiculo)
            if ejecucion is None:
                return {"evento": "sin_demo_activa"}
            ejecucion.motivo = motivo
            ejecucion.cancelar.set()
        await asyncio.shield(ejecucion.tarea)
        return {"evento": "cancelacion_procesada", "id_demo": ejecucion.id_demo}

    async def desconectar(self, vehiculo, socket):
        async with self.locks[vehiculo]:
            if self.hub.dispositivos.get(vehiculo) is not socket:
                return
            self.hub.dispositivos.pop(vehiculo, None)
            self.ordenes.pop(vehiculo, None)
        await self.cancelar(vehiculo, "dispositivo_desconectado")
        async with self.locks[vehiculo]:
            if not self.hub.conectado(vehiculo):
                try:
                    await self.db(self.repo.conexion, vehiculo, False)
                except AppError:
                    logger.warning("No se pudo guardar desconexion del vehiculo %s", vehiculo)
                await self.hub.notificar(vehiculo, {"evento": "dispositivo_desconectado"})

    async def cerrar(self):
        self.cerrando = True
        await asyncio.gather(*(self.cancelar(v, "servidor_cerrando") for v in tuple(self.demos)))
