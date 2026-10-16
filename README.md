# Grúa IoT — API HTTP, MySQL y WebSocket

Servidor local para una grúa con ESP8266. Recibe órdenes, registra estado e
historial mediante procedimientos almacenados y ejecuta secuencias de demos.

**El estado ahora se consulta en MySQL.** `app/data/status.json` se conserva
como archivo antiguo y ya no se lee ni se escribe desde la API.

## Ejecutar en PowerShell

Si aún no existe el entorno virtual:

```powershell
python -m venv .venv
```

Instala las dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si aún no tienes `.env`, copia `.env.example` y completa tus datos de MySQL.
Conserva el `.env` existente si ya contiene tus credenciales. `VEHICULO_ID=1`
selecciona el vehículo de las rutas antiguas `/status` y `/ws`.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Documentación interactiva: http://127.0.0.1:8000/docs
Esquema de la API: http://127.0.0.1:8000/openapi.json

Usa **un solo proceso/worker**. Las conexiones, bloqueos y demos activas se
coordinan en memoria. Durante una demo, un reinicio o recarga cancela la tarea;
la demo no se reanuda automáticamente.

## Base de datos existente

La aplicación usa las tablas y procedimientos de `sql/VeiculoIot.sql` y
`sql/SP.sql`. No ejecuta esos archivos automáticamente ni modifica el esquema
al arrancar. La base local existente ya dispone de ellos.

Para una instalación nueva, el orden es:

1. Crear la base y las tablas: bloque inicial de `VeiculoIot.sql`, hasta
   `SHOW TABLES;`.
2. Ejecutar `SP.sql` para instalar procedimientos y triggers.
3. Ejecutar los datos de ejemplo de `VeiculoIot.sql`, después del primer
   `SHOW TABLES;`, incluidos los comandos 10, 11 y 12.

El comienzo de `VeiculoIot.sql` incluye `DROP DATABASE`; ejecutarlo sobre
una base existente elimina sus datos. No es un script de actualización.

Cada operación de la API usa una conexión independiente. Los SP
`sp_registrar_comando` y `sp_eliminar_vehiculo` administran sus propias
transacciones; los demás se confirman desde Python. Las validaciones internas
`sp_validar_comando` y `sp_validar_movimiento` no se exponen como rutas.

## Rutas HTTP

Son 22 operaciones sobre SP, más dos rutas de compatibilidad.
`{id}` siempre es el identificador del recurso en esa ruta.

| Método y ruta | SP |
| --- | --- |
| POST /vehiculos | sp_crear_vehiculo |
| GET /vehiculos | sp_obtener_vehiculos |
| GET /vehiculos/{id} | sp_obtener_vehiculo |
| PUT /vehiculos/{id} | sp_actualizar_vehiculo |
| DELETE /vehiculos/{id} | sp_eliminar_vehiculo |
| POST /vehiculos/{id}/comandos | sp_crear_comando |
| GET /vehiculos/{id}/comandos | sp_obtener_comandos_vehiculo |
| PUT /comandos/{id} | sp_actualizar_comando |
| DELETE /comandos/{id} | sp_eliminar_comando |
| PUT /vehiculos/{id}/estado | sp_actualizar_estado |
| GET /vehiculos/{id}/estado | sp_obtener_estado |
| POST /vehiculos/{id}/historial | sp_registrar_historial |
| GET /vehiculos/{id}/historial | sp_obtener_historial |
| POST /vehiculos/{id}/demos | sp_crear_demo |
| GET /vehiculos/{id}/demos | sp_obtener_demos |
| PUT /demos/{id} | sp_actualizar_demo |
| DELETE /demos/{id} | sp_eliminar_demo |
| POST /demos/{id}/movimientos | sp_agregar_movimiento_demo |
| GET /demos/{id}/movimientos | sp_obtener_movimientos_demo |
| PUT /movimientos-demo/{id} | sp_actualizar_movimiento_demo |
| DELETE /movimientos-demo/{id} | sp_eliminar_movimiento_demo |
| POST /vehiculos/{id}/movimientos | sp_registrar_comando |

Crear un comando agrega una definición al catálogo. Para enviar una orden,
usa `POST /vehiculos/{id}/movimientos` con `codigo`, no con `id_comando`:

```json
{"codigo": 7, "origen": "MANUAL"}
```

La grúa debe estar conectada en su WebSocket. El servidor resuelve el
`id_comando`, guarda estado e historial juntos y envía la orden. Un fallo de
MySQL impide el envío normal. Un fallo de envío posterior conserva el historial
como registro de la solicitud y devuelve un error; no garantiza ejecución.

Consulta el historial con `GET /vehiculos/1/historial`: devuelve código,
nombre, fecha y origen, del más reciente al más antiguo. Los nombres históricos
son copias del nombre al registrar la solicitud y no cambian al renombrar el
catálogo. Por ahora no hay paginación.

`POST /vehiculos/{id}/historial` acepta `id_comando` y `origen`; solo
registra una entrada. `PUT /vehiculos/{id}/estado` acepta `id_comando`
(o `null`); solo actualiza el estado almacenado. Ninguna de estas dos rutas
acciona la grúa. El campo `conectado` lo determina el servidor por la
conexión del dispositivo, no el cuerpo de la petición.

Se devuelve 404 para recursos inexistentes, 409 para conflictos (duplicados,
referencias, grúa desconectada o demo activa), 422 para datos inválidos y 503
para fallos de base o transporte. No se exponen contraseñas ni mensajes de
conexión de MySQL. Las rutas DELETE conservan el comportamiento de los SP,
incluidas sus eliminaciones en cascada.

## Catálogo de control

| Código | Acción |
| --- | --- |
| 1 | AVANZAR |
| 2 | RETROCEDER |
| 3 | GIRAR_IZQUIERDA |
| 4 | GIRAR_DERECHA |
| 5 | SUBIR_BRAZO |
| 6 | BAJAR_BRAZO |
| 7 | BAJAR_GANCHO |
| 8 | SUBIR_GANCHO |
| 9 | DETENER |
| 10 | ALTERNAR_LUCES |
| 11 | ALTERNAR_SONIDO |
| 12 | EJECUTAR_DEMO |

Los códigos 5 y 6 se conservan hasta definir sus acciones definitivas.
El ejecutor trata 1–8 como movimientos de motores y 9 como detención;
el firmware debe respetar este contrato. Las luces y el sonido alternan una vez
por orden y no se restauran automáticamente al acabar una demo.

## WebSocket y demos

El protocolo completo está en [docs/websocket.md](docs/websocket.md).

- `/ws/vehiculos/{id}`: ESP8266; una conexión por vehículo.
- `/ws/vehiculos/{id}/demos`: interfaz de control y eventos.
- `/ws`: observador antiguo del vehículo configurado en `VEHICULO_ID`.

Para iniciar una demo desde el WebSocket de la interfaz:

```json
{"accion": "iniciar", "id_demo": 1}
```

Para cancelarla:

```json
{"accion": "cancelar"}
```

También se puede iniciar por HTTP:

```json
{"codigo": 12, "id_demo": 1}
```

Una demo debe tener **al menos dos movimientos** antes de ejecutarse, tanto
por HTTP como por WebSocket. Puedes crearla vacía y agregar los pasos uno por
uno en `POST /demos/{id}/movimientos`, usando el mismo `id_demo` y órdenes
1, 2, 3, etc. Con cero o un paso se rechaza el inicio con error 422, sin
registrar el inicio ni enviar movimientos. Si borras pasos y queda menos de
dos, tendrás que completarla antes de volver a ejecutarla.

Una sola demo puede estar activa por grúa. Las otras órdenes manuales se
rechazan mientras corre, excepto 9 (DETENER), que la cancela. No se permite
el código 12 dentro de una secuencia. Se toma una copia de los pasos al iniciar
y se validan los comandos antes de enviarlos.

Cada paso se mantiene durante `duracion_ms`; los códigos de motor reciben
DETENER antes de la `pausa_ms`. Al finalizar o cancelar, se intenta enviar
DETENER. Si MySQL falla durante la demo, se intenta una detención de emergencia
sin registrar, identificada por `registrado: false`.

Al perder el dispositivo se cancela la demo. También se cancela si se cierra la
interfaz que la inició por WebSocket; otros observadores pueden salir sin
cancelarla. Las demos iniciadas por HTTP no tienen interfaz propietaria.

## Compatibilidad

- `GET /status`: devuelve `{"status": codigo}` desde MySQL; puede ser
  `null` si aún no hay comando registrado.
- `POST /status`: acepta `{"status": 7}`, registra y envía al dispositivo
  del vehículo configurado. Requiere conexión y añade información de resultado
  a la respuesta. Para 12 usa la ruta nueva con `id_demo`.
- `/ws`: envía el estado al conectar y cambios posteriores como
  `{"status": 7}`. Es solo observación. El ESP8266 debe migrar a
  `/ws/vehiculos/{id}` para control y confirmaciones.

El último movimiento no se reproduce al reconectar el ESP8266: se envía
DETENER. El JSON antiguo no se utiliza como respaldo ante un fallo de MySQL.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas sin MySQL usan dispositivos y repositorios simulados. Para probar
además los SP y endpoints con MySQL:

```powershell
$env:IOT_TEST_MYSQL = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
Remove-Item Env:IOT_TEST_MYSQL
```

Las pruebas de integración crean una base aleatoria `iot_test_...`, cargan
solo tablas/rutinas en ella y la eliminan al terminar. Requieren permisos de
creación de bases y rutinas. No modifican los datos de `vehiculo_iot` ni
se conectan al hardware.

## Alcance local y AWS

La configuración de MySQL usa variables de entorno con prioridad sobre
`.env`. Para TLS configura `MYSQL_SSL_CA` con la ruta al certificado CA;
se verifican certificado y nombre del servidor.

Esta versión es para pruebas en una red local de confianza: todavía no tiene
autenticación en HTTP ni WebSocket. Antes de exponerla en AWS se necesitan
control de acceso, HTTPS/WSS y configuración de red. Para varios workers o
instancias también hará falta coordinar conexiones y tareas fuera de memoria.

El firmware del ESP8266 no está incluido. Debe implementar los códigos,
las confirmaciones, las duraciones y un mecanismo de detención por pérdida de
conexión; el servidor no puede garantizar detener un dispositivo desconectado.
Las confirmaciones se transmiten a observadores y no se guardan como ejecución
física en el esquema actual. Las demos usan tiempos del servidor, sin esperar
una confirmación física por paso.

Referencias: [Connector/Python y procedimientos](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-callproc.html),
[WebSocket en FastAPI](https://fastapi.tiangolo.com/advanced/websockets/).
