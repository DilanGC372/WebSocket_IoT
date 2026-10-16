-- MySQL 8.0.16 o posterior. Ejecutar el archivo completo en MySQL Workbench.
-- ATENCION: elimina la base vehiculo_iot y todos sus datos actuales.
DROP DATABASE IF EXISTS vehiculo_iot;
CREATE DATABASE vehiculo_iot CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE vehiculo_iot;

CREATE TABLE vehiculos (
 id_vehiculo INT AUTO_INCREMENT PRIMARY KEY,
 nombre VARCHAR(80) NOT NULL,
 modelo VARCHAR(80), descripcion VARCHAR(255), microcontrolador VARCHAR(50),
 fecha_registro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 activo BOOLEAN NOT NULL DEFAULT TRUE,
 CHECK (CHAR_LENGTH(TRIM(nombre)) > 0), CHECK (activo IN (0,1))
) ENGINE=InnoDB;
CREATE TABLE comandos (
 id_comando INT AUTO_INCREMENT PRIMARY KEY,
 id_vehiculo INT NOT NULL, nombre VARCHAR(60) NOT NULL, codigo INT NOT NULL,
 descripcion VARCHAR(255), activo BOOLEAN NOT NULL DEFAULT TRUE,
 UNIQUE (id_vehiculo,codigo), UNIQUE (id_vehiculo,nombre),
 CHECK (CHAR_LENGTH(TRIM(nombre)) > 0), CHECK (activo IN (0,1)),
 FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE estado_vehiculo (
 id_estado INT AUTO_INCREMENT PRIMARY KEY,
 id_vehiculo INT NOT NULL UNIQUE, id_comando INT NULL,
 fecha_actualizacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
 conectado BOOLEAN NOT NULL DEFAULT FALSE, CHECK (conectado IN (0,1)),
 FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo) ON DELETE CASCADE,
 FOREIGN KEY (id_comando) REFERENCES comandos(id_comando) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE TABLE historial_comandos (
 id_historial BIGINT AUTO_INCREMENT PRIMARY KEY,
 id_vehiculo INT NOT NULL, id_comando INT NULL,
 nombre_comando VARCHAR(60) NOT NULL DEFAULT '', codigo_comando INT NOT NULL DEFAULT 0,
 fecha_hora TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
 origen VARCHAR(30) NOT NULL DEFAULT 'MANUAL',
 CHECK (CHAR_LENGTH(TRIM(origen)) > 0),
 INDEX ix_historial_fecha (id_vehiculo,fecha_hora,id_historial),
 FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo) ON DELETE CASCADE,
 FOREIGN KEY (id_comando) REFERENCES comandos(id_comando) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE TABLE demos (
 id_demo INT AUTO_INCREMENT PRIMARY KEY,
 id_vehiculo INT NOT NULL, nombre VARCHAR(80) NOT NULL, descripcion VARCHAR(255),
 activo BOOLEAN NOT NULL DEFAULT TRUE,
 CHECK (CHAR_LENGTH(TRIM(nombre)) > 0), CHECK (activo IN (0,1)),
 FOREIGN KEY (id_vehiculo) REFERENCES vehiculos(id_vehiculo) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE demo_movimientos (
 id_demo_movimiento INT AUTO_INCREMENT PRIMARY KEY,
 id_demo INT NOT NULL, id_comando INT NOT NULL, orden INT NOT NULL,
 duracion_ms INT UNSIGNED NOT NULL, pausa_ms INT UNSIGNED NOT NULL DEFAULT 0,
 UNIQUE (id_demo,orden), CHECK (orden > 0), CHECK (duracion_ms > 0),
 FOREIGN KEY (id_demo) REFERENCES demos(id_demo) ON DELETE CASCADE,
 FOREIGN KEY (id_comando) REFERENCES comandos(id_comando) ON DELETE RESTRICT
) ENGINE=InnoDB;

SHOW TABLES;


-----------------------------------------------------------------------------------------------
-----------------------------------------------------------------------------------------------

CALL sp_crear_vehiculo(

  'Grúa IoT',

  'Modelo X',

  'Vehículo de construcción controlado por ESP8266',

  'ESP8266'

);

CALL sp_crear_comando(1,'AVANZAR',1,'Mover el vehículo hacia adelante');

CALL sp_crear_comando(1,'RETROCEDER',2,'Mover el vehículo hacia atrás');

CALL sp_crear_comando(1,'GIRAR_IZQUIERDA',3,'Giro hacia la izquierda');

CALL sp_crear_comando(1,'GIRAR_DERECHA',4,'Giro hacia la derecha');

CALL sp_crear_comando(1,'SUBIR_BRAZO',5,'Elevar el brazo');

CALL sp_crear_comando(1,'BAJAR_BRAZO',6,'Descender el brazo');

CALL sp_crear_comando(1,'BAJAR_GANCHO',7,'Bajar el gancho');

CALL sp_crear_comando(1,'SUBIR_GANCHO',8,'Subir el gancho');

CALL sp_crear_comando(1,'DETENER',9,'Detener cualquier movimiento');

CALL sp_actualizar_estado(1,9,1);

CALL sp_registrar_historial(1,1,'WORKBENCH');

CALL sp_registrar_historial(1,3,'WORKBENCH');

CALL sp_registrar_historial(1,5,'WORKBENCH');

CALL sp_registrar_historial(1,7,'WORKBENCH');

CALL sp_registrar_historial(1,9,'WORKBENCH');

CALL sp_crear_demo(

  1,

  'Demo principal',

  'Secuencia automática de movimientos del vehículo'

);

CALL sp_agregar_movimiento_demo(1,1,1,2000,400);

CALL sp_agregar_movimiento_demo(1,3,2,1000,300);

CALL sp_agregar_movimiento_demo(1,5,3,1500,300);

CALL sp_agregar_movimiento_demo(1,7,4,900,250);

CALL sp_agregar_movimiento_demo(1,8,5,900,250);

CALL sp_agregar_movimiento_demo(1,6,6,1500,300);

CALL sp_agregar_movimiento_demo(1,2,7,2000,400);

CALL sp_agregar_movimiento_demo(1,9,8,500,0);

CALL sp_obtener_vehiculos();

CALL sp_obtener_comandos_vehiculo(1);

CALL sp_obtener_estado(1);

CALL sp_obtener_historial(1);

CALL sp_obtener_demos(1);

CALL sp_obtener_movimientos_demo(1);


select * from comandos;

-- Ejecutar sobre la base existente, despues de crear las tablas y el vehiculo.
-- Este archivo solo agrega los comandos 10, 11 y 12; no borra datos.
USE vehiculo_iot;

-- El vehiculo de los datos de ejemplo tiene ID 1. Cambiar si corresponde.
SET @id_vehiculo = 1;

-- Ejecutar una sola vez. Si un codigo o nombre ya existe para este vehiculo,
-- las restricciones UNIQUE rechazan el INSERT completo sin sobrescribirlo.
INSERT INTO comandos (id_vehiculo, nombre, codigo, descripcion)
VALUES
    (@id_vehiculo, 'ALTERNAR_LUCES', 10,
     'Encender las luces si estan apagadas o apagarlas si estan encendidas'),
    (@id_vehiculo, 'ALTERNAR_SONIDO', 11,
     'Encender el sonido si esta apagado o apagarlo si esta encendido'),
    (@id_vehiculo, 'EJECUTAR_DEMO', 12,
     'Iniciar una secuencia de movimientos previamente programada');

SELECT id_comando, codigo, nombre, descripcion, activo
FROM comandos
WHERE id_vehiculo = @id_vehiculo
ORDER BY codigo;

-- El programa del carrito debe interpretar estos codigos.
-- El comando 12 no crea ni ejecuta automaticamente las secuencias de las demos.
