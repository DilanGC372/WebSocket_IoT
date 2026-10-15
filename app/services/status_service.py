import json

from pathlib import Path


class StatusService:

    def __init__(self):

        self.archivo = Path(__file__).resolve().parent.parent / "data" / "status.json"


    def obtener_estado(self):

        with open(self.archivo, "r", encoding="utf-8") as archivo:

            return json.load(archivo)


    def guardar_estado(self, status: int):

        nuevo_estado = {"status": status}

        with open(self.archivo, "w", encoding="utf-8") as archivo:

            json.dump(nuevo_estado, archivo, indent=4)

        return nuevo_estado
