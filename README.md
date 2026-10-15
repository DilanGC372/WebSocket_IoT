# Servidor del carrito IoT

API FastAPI para enviar uno de los 12 movimientos del carrito. Cada movimiento
se identifica con un entero del 1 al 12; la asociación entre número y acción
debe definirse en el programa del carrito.

## Ejecutar localmente (PowerShell)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

- `GET /status`: consulta el movimiento guardado.
- `POST /status`: recibe, por ejemplo, `{"status": 3}`, guarda el movimiento
  y lo envía a todos los clientes WebSocket. Rechaza valores fuera del rango,
  booleanos, decimales y cadenas de texto con HTTP 422.
- `/ws`: envía el estado actual al conectar y después los cambios.

El estado inicial del archivo es `1`; todavía no se ha asignado su acción física.

## Preparar MySQL

```powershell
Copy-Item .env.example .env
```

Completa `.env` con el nombre de tu base existente, usuario y contraseña.
Este archivo está excluido de Git. `app/database.py` proporciona
`conectar_base_datos()`; no abre conexiones al importar el módulo ni crea tablas.

Prueba la conexión después de configurar MySQL:

```powershell
.\.venv\Scripts\python.exe -c "from app.database import conectar_base_datos; conexion = conectar_base_datos(); print(conexion.is_connected()); conexion.close()"
```

Quien use la conexión debe cerrarla en un bloque `finally`, confirmar escrituras
con `commit()` y usar `rollback()` si una transacción falla.

**Por ahora, los endpoints siguen guardando el estado en `app/data/status.json`.**
Falta conocer las tablas y columnas de la base existente para integrar las
consultas en `app/services/status_service.py`.

## Configuración para AWS

La conexión toma los mismos parámetros de variables de entorno, que tienen
prioridad sobre `.env`. Para usar MySQL alojado en AWS, configura `MYSQL_HOST`,
`MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD` y `MYSQL_DATABASE` en el despliegue.
Si usas RDS, configura `MYSQL_SSL_CA` con la ruta al certificado CA correspondiente;
el código activa la verificación del certificado y del nombre del servidor.
El acceso de red y las credenciales deberán configurarse al desplegar.

Opciones de conexión: [documentación oficial de MySQL Connector/Python](https://dev.mysql.com/doc/connectors/en/connector-python-connectargs.html).

Antes de usar varias instancias del servidor, habrá que reemplazar el JSON local
por persistencia compartida y coordinar los mensajes WebSocket entre instancias.
