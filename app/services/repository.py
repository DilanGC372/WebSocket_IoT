"""Acceso sincrono a MySQL: cada operacion usa y cierra su conexion."""

import mysql.connector

from app.database import conectar_base_datos
from app.errors import AppError


PROCEDIMIENTOS = {
    "sp_crear_vehiculo", "sp_obtener_vehiculos", "sp_obtener_vehiculo",
    "sp_actualizar_vehiculo", "sp_eliminar_vehiculo", "sp_crear_comando",
    "sp_obtener_comandos_vehiculo", "sp_actualizar_comando", "sp_eliminar_comando",
    "sp_actualizar_estado", "sp_obtener_estado", "sp_registrar_historial",
    "sp_obtener_historial", "sp_crear_demo", "sp_obtener_demos",
    "sp_actualizar_demo", "sp_eliminar_demo", "sp_agregar_movimiento_demo",
    "sp_obtener_movimientos_demo", "sp_actualizar_movimiento_demo",
    "sp_eliminar_movimiento_demo", "sp_registrar_comando",
}
TABLAS = {
    "vehiculos": "id_vehiculo", "comandos": "id_comando",
    "demos": "id_demo", "demo_movimientos": "id_demo_movimiento",
}


class Repository:
    def _operacion(self, trabajo, transaccion_propia=False):
        conexion = None
        cursor = None
        try:
            conexion = conectar_base_datos()
            # Estos dos SP hacen START TRANSACTION/COMMIT internamente.
            if transaccion_propia:
                conexion.autocommit = True
            cursor = conexion.cursor(dictionary=True, buffered=True)
            resultado = trabajo(cursor)
            if not transaccion_propia:
                conexion.commit()
            return resultado
        except mysql.connector.Error as error:
            if conexion:
                conexion.rollback()
            if error.errno in (1062, 1451):
                raise AppError(409, "Registro duplicado o utilizado por otros registros") from error
            if error.errno in (1452, 3819) or error.sqlstate == "45000":
                raise AppError(422, "La operacion incumple las relaciones o validaciones de la base") from error
            raise AppError(503, "No se pudo completar la operacion en MySQL") from error
        except ValueError as error:
            raise AppError(503, "Revisa la configuracion de MySQL") from error
        finally:
            try:
                if cursor:
                    cursor.close()
            finally:
                if conexion:
                    conexion.close()

    def call(self, nombre, args=()):
        if nombre not in PROCEDIMIENTOS:
            raise ValueError("Procedimiento no permitido")

        def ejecutar(cursor):
            cursor.callproc(nombre, tuple(args))
            filas = []
            for resultado in cursor.stored_results():
                filas.extend(resultado.fetchall())
                resultado.close()
            return filas

        return self._operacion(ejecutar, nombre in {"sp_registrar_comando", "sp_eliminar_vehiculo"})

    def get(self, tabla, identificador):
        clave = TABLAS[tabla]

        def consultar(cursor):
            cursor.execute(f"SELECT * FROM {tabla} WHERE {clave} = %s", (identificador,))
            return cursor.fetchone()

        fila = self._operacion(consultar)
        if fila is None:
            raise AppError(404, "Registro no encontrado")
        return fila

    def vehiculo(self, identificador, activo=False):
        fila = self.get("vehiculos", identificador)
        if activo and not fila["activo"]:
            raise AppError(409, "La grua esta desactivada")
        return fila

    def comando(self, vehiculo, codigo):
        self.vehiculo(vehiculo, activo=True)
        filas = self.call("sp_obtener_comandos_vehiculo", (vehiculo,))
        comando = next((fila for fila in filas if fila["codigo"] == codigo), None)
        if comando is None or not comando["activo"]:
            raise AppError(422, "El codigo no existe o esta desactivado para esta grua")
        return comando

    def estado(self, vehiculo):
        self.vehiculo(vehiculo)
        filas = self.call("sp_obtener_estado", (vehiculo,))
        if not filas:
            raise AppError(404, "La grua no tiene estado registrado")
        return filas[0]

    def registrar(self, vehiculo, codigo, conectado, origen):
        comando = self.comando(vehiculo, codigo)
        self.call("sp_registrar_comando", (vehiculo, comando["id_comando"], conectado, origen))
        return comando

    def conexion(self, vehiculo, conectado):
        def actualizar(cursor):
            cursor.execute("UPDATE estado_vehiculo SET conectado = %s WHERE id_vehiculo = %s", (conectado, vehiculo))
        self._operacion(actualizar)

    def actualizar(self, vehiculo, codigo, conectado):
        """Guarda un paso de demo sin insertar historial."""
        comando = self.comando(vehiculo, codigo)
        self.call("sp_actualizar_estado", (vehiculo, comando["id_comando"], conectado))
        return comando

    def secuencia(self, vehiculo, demo):
        self.vehiculo(vehiculo, activo=True)
        fila = self.get("demos", demo)
        if fila["id_vehiculo"] != vehiculo or not fila["activo"]:
            raise AppError(422, "La demo no pertenece a la grua o esta desactivada")
        pasos = self.call("sp_obtener_movimientos_demo", (demo,))
        if len(pasos) < 2:
            raise AppError(422, "La demo debe tener al menos 2 movimientos antes de ejecutarse")
        for paso in pasos:
            comando = self.comando(vehiculo, paso["codigo"])
            if comando["id_comando"] != paso["id_comando"] or paso["codigo"] == 12:
                raise AppError(422, "Una demo no puede contener otras demos ni comandos ajenos")
            if paso["duracion_ms"] <= 0 or paso["pausa_ms"] < 0:
                raise AppError(422, "Duracion o pausa invalida")
        self.comando(vehiculo, 9)
        return pasos
