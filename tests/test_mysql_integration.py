"""Integracion optativa: crea una base temporal y un ESP8266 simulado.
Ejecutar con IOT_TEST_MYSQL=1. Nunca ejecuta el DROP DATABASE del script del proyecto.
"""
import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.database import conectar_base_datos
from app.errors import AppError
from app.main import create_app
from app.services.repository import Repository

ROOT = Path(__file__).resolve().parents[1]


def sentencias(texto):
    delimitador = ";"
    buffer = []
    for linea in texto.splitlines():
        if linea.strip().startswith("--") or not linea.strip():
            continue
        if linea.strip().upper().startswith("DELIMITER "):
            delimitador = linea.strip().split()[1]
            continue
        buffer.append(linea)
        bloque = "\n".join(buffer).strip()
        if bloque.endswith(delimitador):
            yield bloque[:-len(delimitador)].strip()
            buffer = []
    if buffer:
        raise AssertionError("SQL sin terminador")


@unittest.skipUnless(os.getenv("IOT_TEST_MYSQL") == "1", "Requiere IOT_TEST_MYSQL=1; usa una base temporal")
class MySQLIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = "iot_test_" + uuid4().hex
        cls.addClassCleanup(cls.borrar_base)
        c = conectar_base_datos()
        try:
            cur = c.cursor()
            cur.execute(f"CREATE DATABASE `{cls.database}` CHARACTER SET utf8mb4")
            c.database = cls.database
            tablas = (ROOT / "sql/VeiculoIot.sql").read_text(encoding="utf-8")
            tablas = tablas[tablas.index("CREATE TABLE"):tablas.index("SHOW TABLES;")]
            for sql in sentencias(tablas):
                cur.execute(sql)
            rutinas = (ROOT / "sql/SP.sql").read_text(encoding="utf-8")
            for sql in sentencias(rutinas):
                if sql.upper().startswith(("CREATE PROCEDURE ", "CREATE TRIGGER ", "DROP PROCEDURE ", "DROP TRIGGER ")):
                    cur.execute(sql)
            c.commit()
            cur.close()
        finally:
            c.close()
        cls.parche = patch("app.services.repository.conectar_base_datos", cls.conectar_pruebas)
        cls.parche.start()
        cls.addClassCleanup(cls.parche.stop)

    @classmethod
    def conectar_pruebas(cls):
        c = conectar_base_datos()
        c.database = cls.database
        return c

    @classmethod
    def borrar_base(cls):
        # Solo se puede eliminar la base aleatoria creada por esta clase.
        assert re.fullmatch(r"iot_test_[0-9a-f]{32}", cls.database)
        c = conectar_base_datos()
        try:
            cur = c.cursor()
            cur.execute(f"DROP DATABASE IF EXISTS `{cls.database}`")
            cur.close()
        finally:
            c.close()

    def setUp(self):
        self.app = create_app(Repository())
        self.client = TestClient(self.app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        response = self.client.post("/vehiculos", json={"nombre": "Grua simulada"})
        self.assertEqual(response.status_code, 201, response.text)
        self.v = response.json()["id_vehiculo"]
        self.app.state.status_service.id_vehiculo = self.v
        self.comandos = {}
        for codigo in range(1, 13):
            response = self.client.post(f"/vehiculos/{self.v}/comandos",
                                        json={"nombre": f"COMANDO_{codigo}", "codigo": codigo})
            self.assertEqual(response.status_code, 201, response.text)
            self.comandos[codigo] = response.json()["id_comando"]

    def crear_demo(self, codigo=7, duracion=5, pausa=0, segundo=8, cantidad=2):
        response = self.client.post(f"/vehiculos/{self.v}/demos", json={"nombre": "Secuencia"})
        self.assertEqual(response.status_code, 201, response.text)
        demo = response.json()["id_demo"]
        pasos = [(codigo, duracion, pausa), (segundo, 5, 0)]
        for orden, (comando, tiempo, espera) in enumerate(pasos[:cantidad], start=1):
            response = self.client.post(f"/demos/{demo}/movimientos", json={
                "id_comando": self.comandos[comando], "orden": orden,
                "duracion_ms": tiempo, "pausa_ms": espera,
            })
            self.assertEqual(response.status_code, 201, response.text)
        return demo

    def conectar(self, device):
        self.assertEqual(device.receive_json()["evento"], "conectado")
        self.assertEqual(device.receive_json()["codigo"], 9)

    def test_crud_y_errores(self):
        c = self.client
        v = self.v
        self.assertEqual(c.get("/vehiculos").status_code, 200)
        self.assertEqual(c.get(f"/vehiculos/{v}").json()["nombre"], "Grua simulada")
        self.assertEqual(c.put(f"/vehiculos/{v}", json={"nombre": "Grua editada", "activo": True}).status_code, 200)
        self.assertEqual(len(c.get(f"/vehiculos/{v}/comandos").json()), 12)
        duplicado = c.post(f"/vehiculos/{v}/comandos", json={"nombre": "Duplicado", "codigo": 7})
        self.assertEqual(duplicado.status_code, 409)
        cmd = self.comandos[7]
        self.assertEqual(c.put(f"/comandos/{cmd}", json={"nombre": "BAJAR_GANCHO", "codigo": 7, "activo": True}).status_code, 200)
        demo = self.crear_demo()
        self.assertEqual(c.delete(f"/comandos/{cmd}").status_code, 409)
        self.assertEqual(c.get(f"/vehiculos/{v}/demos").status_code, 200)
        self.assertEqual(c.put(f"/demos/{demo}", json={"nombre": "Editada", "activo": True}).status_code, 200)
        paso = c.get(f"/demos/{demo}/movimientos").json()[0]["id_demo_movimiento"]
        self.assertEqual(c.put(f"/movimientos-demo/{paso}", json={
            "id_comando": self.comandos[8], "orden": 1, "duracion_ms": 10, "pausa_ms": 1,
        }).status_code, 200)
        self.assertEqual(c.delete(f"/movimientos-demo/{paso}").status_code, 204)
        self.assertEqual(c.delete(f"/demos/{demo}").status_code, 204)
        self.assertEqual(c.delete(f"/comandos/{cmd}").status_code, 204)
        self.assertEqual(c.delete(f"/vehiculos/{v}").status_code, 204)
        self.assertEqual(c.get(f"/vehiculos/{v}").status_code, 404)

    def test_historial_estado_y_compatibilidad(self):
        c = self.client
        self.assertEqual(c.post(f"/vehiculos/{self.v}/historial",
                               json={"id_comando": self.comandos[7], "origen": "PRUEBA"}).status_code, 201)
        historial = c.get(f"/vehiculos/{self.v}/historial").json()
        self.assertEqual(historial[0]["codigo"], 7)
        self.assertEqual(historial[0]["origen"], "PRUEBA")
        self.assertEqual(c.put(f"/vehiculos/{self.v}/estado", json={"id_comando": self.comandos[9]}).status_code, 200)
        self.assertEqual(c.get("/status").json(), {"status": 9})
        self.assertFalse(c.get(f"/vehiculos/{self.v}/estado").json()["conectado"])
        with c.websocket_connect("/ws") as ws:
            self.assertEqual(ws.receive_json(), {"status": 9})

    def test_validacion_y_grua_desconectada(self):
        c = self.client
        for codigo in [0, 13, True, "7", 7.0]:
            self.assertEqual(c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": codigo}).status_code, 422)
        self.assertEqual(c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": 12}).status_code, 422)
        self.assertEqual(c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": 7}).status_code, 409)
        self.assertEqual(c.get(f"/vehiculos/{self.v}/historial").json(), [])
        demo = c.post(f"/vehiculos/{self.v}/demos", json={"nombre": "Demo"}).json()["id_demo"]
        for datos in [
            {"id_comando": self.comandos[12], "orden": 1, "duracion_ms": 1},
            {"id_comando": self.comandos[7], "orden": 1, "duracion_ms": 0},
        ]:
            self.assertEqual(c.post(f"/demos/{demo}/movimientos", json=datos).status_code, 422)

    def test_movimiento_confirmacion_y_aislamiento(self):
        c = self.client
        other = c.post("/vehiculos", json={"nombre": "Otra grua"}).json()["id_vehiculo"]
        with c.websocket_connect(f"/ws/vehiculos/{self.v}/demos") as observer:
            observer.receive_json()
            with c.websocket_connect(f"/ws/vehiculos/{self.v}") as device:
                self.conectar(device)
                with self.assertRaises(WebSocketDisconnect):
                    with c.websocket_connect(f"/ws/vehiculos/{self.v}"):
                        pass
                self.assertEqual(c.post(f"/vehiculos/{other}/movimientos", json={"codigo": 7}).status_code, 409)
                response = c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": 7})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertFalse(response.json()["ejecucion_confirmada"])
                orden = device.receive_json()
                self.assertEqual(orden["codigo"], 7)
                device.send_json({"evento": "confirmacion", "id_orden": orden["id_orden"], "resultado": "ejecutado"})
                self.assertEqual(observer.receive_json()["resultado"], "ejecutado")
                response = c.post("/status", json={"status": 8})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(device.receive_json()["codigo"], 8)
                historial = c.get(f"/vehiculos/{self.v}/historial").json()
                self.assertEqual([r["codigo"] for r in historial], [8, 7, 9])
            self.assertEqual(observer.receive_json()["evento"], "dispositivo_desconectado")
        self.assertFalse(c.get(f"/vehiculos/{self.v}/estado").json()["conectado"])

    def test_demo_completa_y_luces_sin_doble_alternancia(self):
        demo = self.crear_demo(codigo=10, duracion=5, segundo=11)
        c = self.client
        with c.websocket_connect(f"/ws/vehiculos/{self.v}/demos") as observer:
            observer.receive_json()
            with c.websocket_connect(f"/ws/vehiculos/{self.v}") as device:
                self.conectar(device)
                observer.send_json({"accion": "iniciar", "id_demo": demo})
                self.assertEqual(observer.receive_json()["evento"], "demo_iniciada")
                self.assertEqual(device.receive_json()["codigo"], 10)
                self.assertEqual(observer.receive_json()["evento"], "paso_enviado")
                self.assertEqual(device.receive_json()["codigo"], 11)
                self.assertEqual(observer.receive_json()["evento"], "paso_enviado")
                self.assertEqual(device.receive_json()["codigo"], 9)
                final = observer.receive_json()
                self.assertEqual(final["evento"], "demo_finalizada")
                self.assertFalse(final["ejecucion_confirmada"])
                historial = c.get(f"/vehiculos/{self.v}/historial").json()
                self.assertEqual([r["codigo"] for r in historial], [9, 11, 10, 12, 9])

    def test_minimo_dos_movimientos_por_http_y_websocket(self):
        demo = self.crear_demo(cantidad=0)
        c = self.client
        with c.websocket_connect(f"/ws/vehiculos/{self.v}/demos") as observer:
            observer.receive_json()
            with c.websocket_connect(f"/ws/vehiculos/{self.v}") as device:
                self.conectar(device)
                historial_inicial = c.get(f"/vehiculos/{self.v}/historial").json()
                for cantidad in (0, 1):
                    response = c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": 12, "id_demo": demo})
                    self.assertEqual(response.status_code, 422)
                    self.assertIn("al menos 2 movimientos", response.json()["detail"])
                    observer.send_json({"accion": "iniciar", "id_demo": demo})
                    error = observer.receive_json()
                    self.assertEqual(error["evento"], "error")
                    self.assertEqual(error["codigo"], 422)
                    self.assertIn("al menos 2 movimientos", error["detalle"])
                    self.assertFalse(self.app.state.control.demos)
                    self.assertEqual(c.get(f"/vehiculos/{self.v}/historial").json(), historial_inicial)
                    response = c.post(f"/demos/{demo}/movimientos", json={
                        "id_comando": self.comandos[7 + cantidad], "orden": cantidad + 1,
                        "duracion_ms": 5, "pausa_ms": 0,
                    })
                    self.assertEqual(response.status_code, 201)
                response = c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": 12, "id_demo": demo})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["pasos"], 2)
                enviados = []
                while True:
                    evento = observer.receive_json()
                    if evento["evento"] == "paso_enviado":
                        enviados.append(evento["codigo"])
                    if evento["evento"] in ("demo_finalizada", "demo_error"):
                        self.assertEqual(evento["evento"], "demo_finalizada")
                        break
                self.assertEqual(enviados, [7, 8])
                paso = c.get(f"/demos/{demo}/movimientos").json()[0]["id_demo_movimiento"]
                self.assertEqual(c.delete(f"/movimientos-demo/{paso}").status_code, 204)
                self.assertEqual(c.post(f"/vehiculos/{self.v}/movimientos", json={
                    "codigo": 12, "id_demo": demo,
                }).status_code, 422)

    def test_demo_motor_y_cancelacion_manual(self):
        demo = self.crear_demo(duracion=30000)
        c = self.client
        with c.websocket_connect(f"/ws/vehiculos/{self.v}/demos") as observer:
            observer.receive_json()
            with c.websocket_connect(f"/ws/vehiculos/{self.v}") as device:
                self.conectar(device)
                response = c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": 12, "id_demo": demo})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(observer.receive_json()["evento"], "demo_iniciada")
                self.assertEqual(device.receive_json()["codigo"], 7)
                observer.receive_json()
                self.assertEqual(c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": 1}).status_code, 409)
                self.assertEqual(c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": 12, "id_demo": demo}).status_code, 409)
                self.assertEqual(c.delete(f"/demos/{demo}").status_code, 409)
                response = c.post(f"/vehiculos/{self.v}/movimientos", json={"codigo": 9})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(device.receive_json()["codigo"], 9)
                self.assertEqual(observer.receive_json()["evento"], "demo_cancelada")
                self.assertFalse(self.app.state.control.demos)

    def test_cancelar_por_websocket(self):
        demo = self.crear_demo(duracion=30000)
        c = self.client
        with c.websocket_connect(f"/ws/vehiculos/{self.v}/demos") as observer:
            observer.receive_json()
            with c.websocket_connect(f"/ws/vehiculos/{self.v}") as device:
                self.conectar(device)
                observer.send_json({"accion": "iniciar", "id_demo": demo})
                observer.receive_json()
                device.receive_json()
                observer.receive_json()
                observer.send_json({"accion": "cancelar"})
                self.assertEqual(device.receive_json()["codigo"], 9)
                self.assertEqual(observer.receive_json()["evento"], "demo_cancelada")
                self.assertEqual(observer.receive_json()["evento"], "cancelacion_procesada")

    def test_fallo_de_historial_revierte_estado(self):
        repo = self.app.state.control.repo
        repo.call('sp_actualizar_estado', (self.v, self.comandos[9], False))
        with self.assertRaises(AppError):
            repo.call('sp_registrar_comando', (self.v, self.comandos[7], False, ''))
        self.assertEqual(repo.estado(self.v)['codigo'], 9)
        self.assertEqual(repo.call('sp_obtener_historial', (self.v,)), [])

    def test_desconexion_de_interfaz_cancela_su_demo(self):
        demo = self.crear_demo(duracion=30000)
        c = self.client
        with c.websocket_connect(f'/ws/vehiculos/{self.v}') as device:
            self.conectar(device)
            with c.websocket_connect(f'/ws/vehiculos/{self.v}/demos') as observer:
                observer.receive_json()
                observer.send_json({'accion': 'iniciar', 'id_demo': demo})
                observer.receive_json()
                device.receive_json()
                observer.receive_json()
            self.assertEqual(device.receive_json()['codigo'], 9)
            self.assertFalse(self.app.state.control.demos)

    def test_desconexion_del_dispositivo_cancela_demo(self):
        demo = self.crear_demo(duracion=30000)
        c = self.client
        with c.websocket_connect(f"/ws/vehiculos/{self.v}/demos") as observer:
            observer.receive_json()
            with c.websocket_connect(f"/ws/vehiculos/{self.v}") as device:
                self.conectar(device)
                observer.send_json({"accion": "iniciar", "id_demo": demo})
                observer.receive_json()
                device.receive_json()
                observer.receive_json()
            final = observer.receive_json()
            self.assertEqual(final["evento"], "demo_cancelada")
            self.assertFalse(final["detener_enviado"])
            self.assertEqual(observer.receive_json()["evento"], "dispositivo_desconectado")
            self.assertFalse(self.app.state.control.demos)


if __name__ == "__main__":
    unittest.main()
