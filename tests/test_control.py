import asyncio
import unittest

from app.errors import AppError
from app.models.api import MovimientoCrear
from app.services.demo_service import ControlGrua


class FakeRepository:
    def __init__(self):
        self.registros = []
        self.fail = set()
        self.pasos = [
            {"codigo": 7, "orden": 1, "duracion_ms": 5, "pausa_ms": 5},
            {"codigo": 8, "orden": 2, "duracion_ms": 5, "pausa_ms": 0},
        ]

    def registrar(self, vehiculo, codigo, conectado, origen):
        if codigo in self.fail:
            raise AppError(503, "Fallo simulado de MySQL")
        self.registros.append((vehiculo, codigo, origen))
        return {"nombre": f"COMANDO_{codigo}"}

    def secuencia(self, vehiculo, demo):
        return self.pasos

    def conexion(self, vehiculo, conectado):
        pass


class FakeSocket:
    def __init__(self, fail=False):
        self.mensajes = []
        self.fail = fail

    async def send_json(self, mensaje):
        if self.fail:
            raise RuntimeError("Transporte roto")
        self.mensajes.append(mensaje)

    async def close(self, code=1000):
        pass


class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repo = FakeRepository()
        self.control = ControlGrua(self.repo)
        self.device = FakeSocket()
        self.observer = FakeSocket()
        self.control.hub.dispositivos[1] = self.device
        self.control.hub.observadores[1].add(self.observer)

    async def asyncTearDown(self):
        await self.control.cerrar()

    async def test_error_mysql_no_envia_movimiento(self):
        self.repo.fail.add(7)
        with self.assertRaises(AppError) as error:
            await self.control.movimiento(1, MovimientoCrear(codigo=7))
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(self.device.mensajes, [])

    async def test_error_envio_conserva_registro_sin_confirmar(self):
        self.device.fail = True
        with self.assertRaises(AppError) as error:
            await self.control.movimiento(1, MovimientoCrear(codigo=7))
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(self.repo.registros, [(1, 7, "MANUAL")])

    async def test_demo_motor_envia_detener_antes_de_pausa_y_al_final(self):
        await self.control.iniciar(1, 1)
        await asyncio.wait_for(self.control.demos[1].tarea, 2)
        self.assertEqual([m["codigo"] for m in self.device.mensajes], [7, 9, 8, 9, 9])
        self.assertEqual(self.observer.mensajes[-1]["evento"], "demo_finalizada")
        self.assertFalse(self.control.demos)

    async def test_error_mysql_en_demo_intenta_detener_de_emergencia(self):
        self.repo.fail.update([7, 9])
        await self.control.iniciar(1, 1)
        await asyncio.wait_for(self.control.demos[1].tarea, 2)
        self.assertEqual([m["codigo"] for m in self.device.mensajes], [9])
        self.assertFalse(self.device.mensajes[0]["registrado"])
        self.assertEqual(self.observer.mensajes[-1]["evento"], "demo_error")

    async def test_demos_por_grua_y_rechazo_simultaneo(self):
        self.repo.pasos[0]["duracion_ms"] = 30000
        segundo = FakeSocket()
        self.control.hub.dispositivos[2] = segundo
        await self.control.iniciar(1, 1)
        with self.assertRaises(AppError):
            await self.control.iniciar(1, 1)
        await self.control.movimiento(2, MovimientoCrear(codigo=8))
        self.assertEqual([m["codigo"] for m in segundo.mensajes], [8])
        await self.control.cancelar(1)
        self.assertEqual(self.device.mensajes[-1]["codigo"], 9)

    async def test_apagado_cancela_demo(self):
        self.repo.pasos[0]["duracion_ms"] = 30000
        await self.control.iniciar(1, 1)
        await asyncio.wait_for(self.control.cerrar(), 2)
        self.assertFalse(self.control.demos)
        self.assertEqual(self.device.mensajes[-1]["codigo"], 9)
        with self.assertRaises(AppError):
            await self.control.iniciar(1, 1)


if __name__ == "__main__":
    unittest.main()
