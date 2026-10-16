# Protocolo de la grúa

## Dispositivo ESP8266

Conectar a `ws://127.0.0.1:8000/ws/vehiculos/1` desde pruebas en la misma
computadora. En el ESP8266 usa la IP de la computadora en la red local.
Solo se permite una conexión por vehículo.

El primer mensaje es:

```json
{"evento": "conectado", "id_vehiculo": 1}
```

Después se registra y envía una orden de DETENER (9). No se reproduce el
comando anterior. Una orden normal tiene este formato:

```json
{
  "evento": "orden",
  "id_orden": "uuid",
  "id_vehiculo": 1,
  "codigo": 7,
  "status": 7,
  "comando": "BAJAR_GANCHO",
  "origen": "MANUAL"
}
```

En un paso de demo también se incluye `duracion_ms`. `status` repite
`codigo` para facilitar la adaptación del firmware. El firmware debe
interpretar una sola acción por mensaje, no una por cada campo.

El servidor interpreta 12 como inicio de demo y envía sus pasos al dispositivo;
no transmite el código 12 al firmware. 10 y 11 son alternancias y no se
reenvían automáticamente. El firmware debe deduplicar por `id_orden` si
implementa reintentos en su propio transporte.

Respuesta del dispositivo:

```json
{"evento": "confirmacion", "id_orden": "uuid", "resultado": "recibido"}
```

`resultado` acepta `recibido`, `ejecutado` o `error`. El identificador
debe pertenecer a una orden de la conexión actual. Se conservan las últimas
256 órdenes pendientes en memoria. Al confirmar ejecución o error se retira
la orden de esa lista. Estas confirmaciones se retransmiten a las interfaces,
pero no se persisten en MySQL ni cambian automáticamente el estado registrado.

Si falla MySQL durante una demo, el servidor intenta enviar:

```json
{"evento": "orden", "codigo": 9, "status": 9, "origen": "EMERGENCIA", "registrado": false}
```

El firmware debe aceptar esta orden de detención incluso sin `id_orden`.
Debe detenerse por sí mismo si pierde la conexión; ningún envío del servidor
puede reemplazar ese mecanismo.

## Interfaz de demos

Conectar a `ws://127.0.0.1:8000/ws/vehiculos/1/demos`.
Al conectar recibe `estado_demo`, con `id_demo` (o null) y `conectado`.

Iniciar:

La demo debe tener al menos dos movimientos guardados. Si tiene cero o uno,
se recibe un evento `error` con código 422 y no comienza la secuencia.

```json
{"accion": "iniciar", "id_demo": 1}
```

Cancelar:

```json
{"accion": "cancelar"}
```

Eventos posibles:

| Evento | Significado |
| --- | --- |
| estado_demo | Estado al conectar la interfaz |
| demo_iniciada | Secuencia validada y programada |
| paso_enviado | Paso transmitido; incluye orden, código e id_orden |
| confirmacion | Respuesta recibida del ESP8266 |
| demo_finalizada | Terminó el envío temporizado de la secuencia |
| demo_cancelada | Se canceló la secuencia |
| demo_error | Falló registro, validación o envío |
| cancelacion_procesada | Respuesta a la solicitud de cancelar |
| sin_demo_activa | No había secuencia que cancelar |
| dispositivo_desconectado | Se perdió la conexión del ESP8266 |
| error | Solicitud inválida o conflicto; incluye detalle y código HTTP equivalente |

El evento terminal incluye `detener_enviado` y
`ejecucion_confirmada: false`. Terminar una secuencia enviada no demuestra
que el equipo haya completado físicamente los movimientos.

Una interfaz que inició una demo por WebSocket es su propietaria: cerrarla
cancela esa demo. Otras interfaces observadoras no la cancelan al salir.
Una demo iniciada por HTTP continúa aunque un observador se desconecte.
