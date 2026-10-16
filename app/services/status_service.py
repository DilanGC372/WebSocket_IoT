"""Compatibilidad de /status: el estado procede de MySQL."""
import os

from dotenv import load_dotenv
from pathlib import Path


class StatusService:
    def __init__(self, repository):
        self.repo = repository
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        self.id_vehiculo = int(os.getenv("VEHICULO_ID", "1"))
        if self.id_vehiculo <= 0:
            raise ValueError("VEHICULO_ID debe ser positivo")

    def obtener_estado(self):
        estado = self.repo.estado(self.id_vehiculo)
        return {"status": estado["codigo"]}
