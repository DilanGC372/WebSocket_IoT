"""Conexión MySQL configurable para desarrollo local y despliegue en AWS."""

import os
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv


def conectar_base_datos():
    """Abre una conexión; quien la utilice debe cerrarla al terminar."""
    # Las variables del entorno de despliegue tienen prioridad sobre .env.
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

    for variable in ("MYSQL_USER", "MYSQL_DATABASE"):
        if not os.getenv(variable):
            raise ValueError(f"Falta configurar {variable} en el entorno o en .env")

    config = {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.environ["MYSQL_USER"],
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.environ["MYSQL_DATABASE"],
        "connection_timeout": 10,
        "autocommit": False,
    }

    certificado_ca = os.getenv("MYSQL_SSL_CA")
    if certificado_ca:
        config.update(
            ssl_ca=certificado_ca,
            ssl_verify_cert=True,
            ssl_verify_identity=True,
        )

    return mysql.connector.connect(**config)
