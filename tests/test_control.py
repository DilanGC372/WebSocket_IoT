import asyncio
import unittest
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.errors import AppError
from app.models.api import MovimientoCrear
from app.services.demo_service import ControlGrua
from app.main import create_app
from app.services.repository import Repository


class FakeRepository:
    def __init__(self):
        self.registros = []
        self.estados = []
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

    def actualizar(self, vehiculo, codigo, conectado):
        if codigo in self.fail:
            raise AppError(503, "Fallo simulado de MySQL")
        self.estados.append((vehiculo, codigo, conectado))
        return {"nombre": f"COMANDO_{codigo}"}

    def estado(self, vehiculo):
        codigo = next((codigo for v, codigo, _ in reversed(self.estados) if v == vehiculo), None)
        return {"codigo": codigo, "conectado": False}

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

    async def test_simulacion_registra_codigos_1_a_11_y_notifica_estado(self):
        self.control.hub.dispositivos.pop(1)
        monitor = FakeSocket()
        self.control.hub.legacy[1].add(monitor)
        with patch.object(self.repo, "registrar", wraps=self.repo.registrar) as registrar:
            for codigo in range(1, 12):
                resultado = await self.control.movimiento(1, MovimientoCrear(codigo=codigo))
                registrar.assert_called_with(1, codigo, False, "MANUAL")
                self.assertTrue(resultado["registrado"])
                self.assertEqual(resultado["modo"], "simulacion")
                self.assertFalse(resultado["enviado_al_dispositivo"])
                self.assertFalse(resultado["ejecucion_confirmada"])
                self.assertEqual(monitor.mensajes[-1], {"status": codigo})
        self.assertEqual(len(self.repo.registros), 11)
        self.assertEqual(self.device.mensajes, [])
        self.assertFalse(self.control.ordenes)

    async def test_simulacion_no_notifica_si_mysql_falla(self):
        self.control.hub.dispositivos.pop(1)
        self.control.hub.legacy[1].add(self.observer)
        self.repo.fail.add(7)
        with self.assertRaises(AppError) as error:
            await self.control.movimiento(1, MovimientoCrear(codigo=7))
        self.assertEqual(error.exception.status_code, 503)
        self.assertEqual(self.repo.registros, [])
        self.assertEqual(self.observer.mensajes, [])

    async def test_demo_sin_dispositivo_respeta_secuencia_tiempos_y_no_historial(self):
        self.control.hub.dispositivos.pop(1)
        monitor = FakeSocket()
        self.control.hub.legacy[1].add(monitor)
        inicio = time.monotonic()
        resultado = await self.control.movimiento(1, MovimientoCrear(codigo=12, id_demo=1))
        self.assertEqual(resultado["modo"], "simulacion")
        await asyncio.wait_for(self.control.demos[1].tarea, 2)
        self.assertGreaterEqual(time.monotonic() - inicio, 0.015)
        self.assertEqual(self.repo.estados, [(1, n, False) for n in (12, 7, 9, 8, 9, 9)])
        self.assertEqual([m["status"] for m in monitor.mensajes], [12, 7, 9, 8, 9, 9])
        self.assertEqual(self.repo.registros, [])
        self.assertEqual(self.device.mensajes, [])
        self.assertFalse(self.control.ordenes)
        self.assertFalse(self.control.demos)
        pasos = [m for m in self.observer.mensajes if m["evento"] == "paso_simulado"]
        self.assertEqual([m["codigo"] for m in pasos], [7, 8])
        self.assertTrue(all(m["id_orden"] is None for m in pasos))
        self.assertEqual(self.observer.mensajes[-1]["evento"], "demo_finalizada")
        self.assertFalse(self.observer.mensajes[-1]["detener_enviado"])

    async def test_cancelacion_manual_de_demo_simulada_registra_solo_detener(self):
        self.control.hub.dispositivos.pop(1)
        self.repo.pasos[0]["duracion_ms"] = 30000
        await self.control.iniciar(1, 1)
        with self.assertRaises(AppError):
            await self.control.movimiento(1, MovimientoCrear(codigo=7))
        with self.assertRaises(AppError):
            await self.control.iniciar(1, 1)
        await asyncio.wait_for(self.control.movimiento(1, MovimientoCrear(codigo=9)), 2)
        self.assertEqual(self.repo.registros, [(1, 9, "MANUAL")])
        self.assertEqual(self.repo.estados[-1], (1, 9, False))
        self.assertFalse(self.control.demos)

    async def test_error_en_simulacion_no_envia_ordenes(self):
        self.control.hub.dispositivos.pop(1)
        self.repo.fail.update([7, 9])
        await self.control.iniciar(1, 1)
        await asyncio.wait_for(self.control.demos[1].tarea, 2)
        self.assertEqual(self.observer.mensajes[-1]["evento"], "demo_error")
        self.assertEqual(self.repo.registros, [])
        self.assertEqual(self.device.mensajes, [])
        self.assertFalse(self.control.demos)

    async def test_fallo_al_iniciar_no_crea_tarea(self):
        self.repo.fail.add(12)
        with self.assertRaises(AppError):
            await self.control.iniciar(1, 1)
        self.assertFalse(self.control.demos)
        self.assertEqual(self.repo.registros, [])

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

        self.assertEqual(self.repo.registros, [])
        self.assertTrue(all(conectado for _, _, conectado in self.repo.estados))

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


class SimulacionHTTPTests(unittest.TestCase):
    def test_demo_http_sin_websockets_termina_en_detener_sin_historial(self):
        repo = FakeRepository()
        app = create_app(repo)
        with TestClient(app) as client:
            respuesta = client.post("/vehiculos/1/movimientos", json={"codigo": 12, "id_demo": 1})
            self.assertEqual(respuesta.status_code, 200, respuesta.text)
            self.assertEqual(respuesta.json()["evento"], "demo_iniciada")
            self.assertEqual(respuesta.json()["modo"], "simulacion")
            async def esperar():
                ejecucion = app.state.control.demos.get(1)
                if ejecucion:
                    await asyncio.wait_for(ejecucion.tarea, 2)
            client.portal.call(esperar)
            estado = client.get("/vehiculos/1/estado")
            self.assertEqual(estado.status_code, 200)
            self.assertEqual(estado.json()["codigo"], 9)
            self.assertEqual(repo.registros, [])
            self.assertEqual([n for _, n, _ in repo.estados], [12, 7, 9, 8, 9, 9])

    def test_repositorio_demo_usa_solo_sp_actualizar_estado(self):
        repo = Repository()
        with patch.object(repo, "comando", return_value={"id_comando": 87}) as validar:
            with patch.object(repo, "call", return_value=[]) as llamada:
                repo.actualizar(3, 8, False)
                validar.assert_called_once_with(3, 8)
                llamada.assert_called_once_with("sp_actualizar_estado", (3, 87, False))

    def test_post_sin_dispositivo_y_errores_del_repositorio(self):
        repo = FakeRepository()
        with TestClient(create_app(repo)) as client:
            respuesta = client.post("/vehiculos/1/movimientos", json={"codigo": 8})
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(respuesta.json()["modo"], "simulacion")
            self.assertEqual(repo.registros, [(1, 8, "MANUAL")])
            for status in (404, 409, 422, 503):
                with patch.object(repo, "registrar", side_effect=AppError(status, "Error de prueba")):
                    respuesta = client.post("/vehiculos/1/movimientos", json={"codigo": 8})
                    self.assertEqual(respuesta.status_code, status)
            self.assertEqual(repo.registros, [(1, 8, "MANUAL")])
            self.assertEqual(client.post("/vehiculos/1/movimientos", json={"codigo": 8, "id_demo": 1}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
