# Prompts de los apuntes

Generados con la herramienta integrada image_gen.

## Hoja 1

Use case: scientific-educational. Genera UNA imagen vertical de alta resolución de una hoja de apuntes manuscritos en español, vista frontal plana, papel cuadriculado blanco crema, tinta azul oscuro, letra manual de imprenta muy clara, títulos con resaltador celeste, números circulados y detalles amarillos/verdes. Estilo cuaderno universitario cuidado, sin manos, sin escritorio, sin adornos que resten espacio. Prioridad absoluta legibilidad y exactitud de rutas y JSON. Siete bloques numerados, espaciados, con distribución inteligente en dos columnas si ayuda. NO omitir ni inventar contenido, NO modificar los números de las APIs. URLs y JSON escritos a mano pero nítidos. Cada bloque incluye título, método/ruta, función y uso. Es una guía educativa, no evidencia de pruebas ejecutadas. No credenciales. Mantener todo dentro de márgenes.
Texto exacto a incluir:
Título: "Grúa IoT · 21 APIs"
Subtítulo: "Hoja 1/3 · Vehículos y comandos"
Recuadro inicial:
"Base: http://54.162.56.226:8000"
"Thunder Client: método + Base/ruta → Body JSON cuando corresponda → Send."
"Swagger: /docs → Try it out → datos → Execute."
"GET y DELETE: sin Body. Los IDs de ejemplo deben existir."

1. Crear vehículo
POST /vehiculos
Registra un vehículo en RDS y crea su estado inicial.
Body: {"nombre":"Grúa de prueba","modelo":"X","descripcion":"Práctica","microcontrolador":"ESP8266"}
Respuesta: 201 + id_vehiculo. Guarda ese ID.

2. Listar vehículos
GET /vehiculos
Consulta los vehículos registrados.
Uso: enviar sin Body.
Respuesta: 200 + lista JSON.

3. Consultar un vehículo
GET /vehiculos/1
Busca el vehículo con ID 1.
Respuesta: 200 + sus datos; 404 si no existe.

4. Actualizar vehículo
PUT /vehiculos/1
Modifica sus datos y su condición de activo.
Body: {"nombre":"Grúa IoT","modelo":"X","descripcion":"Actualizada","microcontrolador":"ESP8266","activo":true}
Respuesta: 200 + datos actualizados.

5. Eliminar vehículo
DELETE /vehiculos/1
Elimina el vehículo y sus datos relacionados.
Uso: sustituir 1 por un vehículo de prueba.
Respuesta: 204, sin cuerpo.
¡Esta operación borra datos!

6. Crear comando
POST /vehiculos/1/comandos
Agrega una acción al catálogo del vehículo; no la ejecuta.
Body: {"nombre":"AVANZAR","codigo":1,"descripcion":"Hacia delante"}
Respuesta: 201 + id_comando.
El código debe estar disponible en ese vehículo.

7. Listar comandos
GET /vehiculos/1/comandos
Devuelve su catálogo ordenado por código.
Respuesta: 200 + lista.
Anota id_comando, codigo y activo.
Recordatorio: id_comando identifica el registro; codigo identifica la acción.

## Hoja 2

Use case: scientific-educational. Genera UNA imagen vertical de alta resolución de una hoja de apuntes manuscritos en español, vista frontal plana, papel cuadriculado blanco crema, tinta azul oscuro, letra manual de imprenta muy clara, títulos con resaltador celeste, números circulados y detalles amarillos/verdes. Estilo cuaderno universitario cuidado, sin manos, sin escritorio, sin adornos que resten espacio. Prioridad absoluta legibilidad y exactitud de rutas y JSON. Siete bloques numerados, espaciados, con distribución inteligente en dos columnas si ayuda. NO omitir ni inventar contenido, NO modificar los números de las APIs. URLs y JSON escritos a mano pero nítidos. Cada bloque incluye título, método/ruta, función y uso. Es una guía educativa, no evidencia de pruebas ejecutadas. No credenciales. Mantener todo dentro de márgenes.
Texto exacto a incluir:
Título: "Grúa IoT · 21 APIs"
Subtítulo: "Hoja 2/3 · Comandos, estado e historial"
Recuadro: "Base: http://54.162.56.226:8000"
"En Thunder Client: método + Base/ruta. Para POST/PUT: Body → JSON → Send."
"Ejemplos: vehículo 1 y comando 1; comprobar que existan y pertenezcan al mismo vehículo."

8. Actualizar comando
PUT /comandos/1
Edita el comando con id_comando 1.
Body: {"nombre":"AVANZAR","codigo":1,"descripcion":"Hacia delante","activo":true}
Respuesta: 200 + comando actualizado.
Requiere dispositivo desconectado y sin demo en ejecución.

9. Eliminar comando
DELETE /comandos/1
Borra el comando del catálogo.
Sin Body. Respuesta: 204.
Puede devolver 409 si un paso de demo lo utiliza.
Usar un comando de prueba.

10. Actualizar estado
PUT /vehiculos/1/estado
Cambia el último comando guardado del vehículo.
Body: {"id_comando":1}
Respuesta: 200 + estado actualizado.
No ejecuta movimiento, no genera historial ni notificación WebSocket.
La conexión la determina el servidor.

11. Consultar estado
GET /vehiculos/1/estado
Lee el último comando, código, fecha y conexión.
Sin Body. Respuesta: 200 + estado.
conectado=false es normal en simulación sin dispositivo.

12. Registrar historial
POST /vehiculos/1/historial
Inserta un registro del comando en el historial.
Body: {"id_comando":1,"origen":"MANUAL"}
Respuesta: 201 + registrado=true.
Solo registra: no ejecuta ni actualiza el estado.

13. Consultar historial
GET /vehiculos/1/historial
Obtiene los registros del vehículo, del más reciente al más antiguo.
Sin Body. Respuesta: 200 + lista JSON.
No elimina registros.
Pendiente de verificar en RDS: máximo 10 y exclusión de DEMO.

14. Crear demo
POST /vehiculos/1/demos
Crea la definición de una secuencia para el vehículo.
Body: {"nombre":"Demo de prueba","descripcion":"Secuencia de movimientos"}
Respuesta: 201 + id_demo.
Guarda el ID: después debes agregar sus pasos.
Crear una demo NO la inicia.

## Hoja 3

Use case: scientific-educational. Genera UNA imagen vertical de alta resolución de una hoja de apuntes manuscritos en español, vista frontal plana, papel cuadriculado blanco crema, tinta azul oscuro, letra manual de imprenta muy clara, títulos con resaltador celeste, números circulados y detalles amarillos/verdes. Estilo cuaderno universitario cuidado, sin manos, sin escritorio, sin adornos que resten espacio. Prioridad absoluta legibilidad y exactitud de rutas y JSON. Siete bloques numerados, espaciados, con distribución inteligente en dos columnas si ayuda. NO omitir ni inventar contenido, NO modificar los números de las APIs. URLs y JSON escritos a mano pero nítidos. Cada bloque incluye título, método/ruta, función y uso. Es una guía educativa, no evidencia de pruebas ejecutadas. No credenciales. Mantener todo dentro de márgenes.
Texto exacto a incluir:
Título: "Grúa IoT · 21 APIs"
Subtítulo: "Hoja 3/3 · Demos y pasos"
Recuadro: "Base: http://54.162.56.226:8000"
"POST/PUT llevan Body JSON. GET/DELETE no llevan Body."
"IDs de ejemplo: demo 1, paso 1, comando 1. Sustituir por los reales."

15. Listar demos
GET /vehiculos/1/demos
Consulta las demos del vehículo 1.
Respuesta: 200 + lista con id_demo, nombre y activo.

16. Actualizar demo
PUT /demos/1
Modifica la definición de la demo 1.
Body: {"nombre":"Demo principal","descripcion":"Secuencia de prueba","activo":true}
Respuesta: 200 + demo actualizada.

17. Eliminar demo
DELETE /demos/1
Borra la demo y sus pasos.
Respuesta: 204, sin cuerpo.
Usar una demo de prueba; no durante su ejecución.

18. Agregar paso
POST /demos/1/movimientos
Añade un comando a la secuencia.
Body: {"id_comando":1,"orden":1,"duracion_ms":2000,"pausa_ms":400}
Respuesta: 201 + paso registrado.
Comando activo del mismo vehículo; código 12 no permitido.

19. Consultar pasos
GET /demos/1/movimientos
Lista los pasos en orden con comando, duración y pausa.
Respuesta: 200 + lista.
2000 ms = 2 segundos; 400 ms = 0.4 segundos.

20. Actualizar paso
PUT /movimientos-demo/1
Edita el paso con id_demo_movimiento 1.
Body: {"id_comando":1,"orden":1,"duracion_ms":1500,"pausa_ms":300}
Respuesta: 200 + paso actualizado.
Duración > 0; pausa ≥ 0; orden positivo.

21. Eliminar paso
DELETE /movimientos-demo/1
Quita ese paso; conserva la demo.
Sin Body. Respuesta: 204.
Para ejecutar, la demo debe conservar al menos dos pasos.

Recuadro final destacado: "Extra: ejecutar ≠ crear"
"Control adicional a las 21 APIs:"
"POST /vehiculos/1/movimientos"
"Individual: {"codigo":1,"origen":"MANUAL"}"
"DEMO: {"codigo":12,"id_demo":1}"
"Individual: estado + historial. DEMO: pasos temporizados, estado y eventos, sin historial."
"Sin dispositivo: simulación. 200 al iniciar no significa demo terminada."
