-- Ejecutar despues de 01_base_y_tablas.sql. MySQL 8.0.16 o posterior.
USE vehiculo_iot;

-- Permite volver a ejecutar este archivo sin borrar las tablas ni sus datos.
DROP PROCEDURE IF EXISTS sp_validar_comando;
DROP PROCEDURE IF EXISTS sp_validar_movimiento;
DROP TRIGGER IF EXISTS tr_vehiculo_estado;
DROP TRIGGER IF EXISTS tr_vehiculo_identidad;
DROP TRIGGER IF EXISTS tr_comando_identidad;
DROP TRIGGER IF EXISTS tr_demo_identidad;
DROP TRIGGER IF EXISTS tr_estado_insertar;
DROP TRIGGER IF EXISTS tr_estado_actualizar;
DROP TRIGGER IF EXISTS tr_historial_insertar;
DROP TRIGGER IF EXISTS tr_historial_actualizar;
DROP TRIGGER IF EXISTS tr_movimiento_insertar;
DROP TRIGGER IF EXISTS tr_movimiento_actualizar;
DROP PROCEDURE IF EXISTS sp_crear_vehiculo;
DROP PROCEDURE IF EXISTS sp_obtener_vehiculos;
DROP PROCEDURE IF EXISTS sp_obtener_vehiculo;
DROP PROCEDURE IF EXISTS sp_actualizar_vehiculo;
DROP PROCEDURE IF EXISTS sp_eliminar_vehiculo;
DROP PROCEDURE IF EXISTS sp_crear_comando;
DROP PROCEDURE IF EXISTS sp_obtener_comandos_vehiculo;
DROP PROCEDURE IF EXISTS sp_actualizar_comando;
DROP PROCEDURE IF EXISTS sp_eliminar_comando;
DROP PROCEDURE IF EXISTS sp_actualizar_estado;
DROP PROCEDURE IF EXISTS sp_obtener_estado;
DROP PROCEDURE IF EXISTS sp_registrar_historial;
DROP PROCEDURE IF EXISTS sp_obtener_historial;
DROP PROCEDURE IF EXISTS sp_crear_demo;
DROP PROCEDURE IF EXISTS sp_obtener_demos;
DROP PROCEDURE IF EXISTS sp_actualizar_demo;
DROP PROCEDURE IF EXISTS sp_eliminar_demo;
DROP PROCEDURE IF EXISTS sp_agregar_movimiento_demo;
DROP PROCEDURE IF EXISTS sp_obtener_movimientos_demo;
DROP PROCEDURE IF EXISTS sp_actualizar_movimiento_demo;
DROP PROCEDURE IF EXISTS sp_eliminar_movimiento_demo;
DROP PROCEDURE IF EXISTS sp_registrar_comando;

-- Validaciones compartidas. Los bloqueos conservan las relaciones durante la escritura.
DELIMITER $$
CREATE PROCEDURE sp_validar_comando(IN p_vehiculo INT, IN p_comando INT)
BEGIN
 DECLARE v_activo BOOLEAN DEFAULT NULL;
 DECLARE c_vehiculo INT DEFAULT NULL;
 DECLARE c_activo BOOLEAN DEFAULT NULL;
 SELECT activo INTO v_activo FROM vehiculos WHERE id_vehiculo=p_vehiculo FOR SHARE;
 IF v_activo IS NULL OR v_activo=FALSE THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='El vehiculo no existe o esta desactivado';
 END IF;
 SELECT id_vehiculo,activo INTO c_vehiculo,c_activo FROM comandos WHERE id_comando=p_comando FOR SHARE;
 IF c_vehiculo IS NULL OR c_vehiculo<>p_vehiculo OR c_activo=FALSE THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='El comando no pertenece al vehiculo o esta desactivado';
 END IF;
END$$
CREATE PROCEDURE sp_validar_movimiento(IN p_demo INT, IN p_comando INT)
BEGIN
 DECLARE v_vehiculo INT DEFAULT NULL;
 DECLARE v_activo BOOLEAN DEFAULT NULL;
 SELECT id_vehiculo,activo INTO v_vehiculo,v_activo FROM demos WHERE id_demo=p_demo FOR SHARE;
 IF v_vehiculo IS NULL OR v_activo=FALSE THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='La demo no existe o esta desactivada';
 END IF;
 CALL sp_validar_comando(v_vehiculo,p_comando);
END$$
CREATE TRIGGER tr_vehiculo_estado AFTER INSERT ON vehiculos FOR EACH ROW
BEGIN
 INSERT INTO estado_vehiculo(id_vehiculo) VALUES(NEW.id_vehiculo);
END$$
-- Los identificadores y la pertenencia son permanentes; crear otro registro para reasignar.
CREATE TRIGGER tr_vehiculo_identidad BEFORE UPDATE ON vehiculos FOR EACH ROW
BEGIN
 IF NEW.id_vehiculo<>OLD.id_vehiculo THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='No se puede cambiar el identificador del vehiculo';
 END IF;
END$$
CREATE TRIGGER tr_comando_identidad BEFORE UPDATE ON comandos FOR EACH ROW
BEGIN
 IF NEW.id_comando<>OLD.id_comando OR NEW.id_vehiculo<>OLD.id_vehiculo THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='No se puede reasignar un comando ni cambiar su identificador';
 END IF;
END$$
CREATE TRIGGER tr_demo_identidad BEFORE UPDATE ON demos FOR EACH ROW
BEGIN
 IF NEW.id_demo<>OLD.id_demo OR NEW.id_vehiculo<>OLD.id_vehiculo THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='No se puede reasignar una demo ni cambiar su identificador';
 END IF;
END$$
CREATE TRIGGER tr_estado_insertar BEFORE INSERT ON estado_vehiculo FOR EACH ROW
BEGIN
 IF NEW.id_comando IS NOT NULL THEN CALL sp_validar_comando(NEW.id_vehiculo,NEW.id_comando); END IF;
END$$
CREATE TRIGGER tr_estado_actualizar BEFORE UPDATE ON estado_vehiculo FOR EACH ROW
BEGIN
 IF NEW.id_vehiculo<>OLD.id_vehiculo THEN
  SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='No se puede reasignar un estado';
 END IF;
 IF NEW.id_comando IS NOT NULL THEN CALL sp_validar_comando(NEW.id_vehiculo,NEW.id_comando); END IF;
END$$
CREATE TRIGGER tr_historial_insertar BEFORE INSERT ON historial_comandos FOR EACH ROW
BEGIN
 DECLARE v_nombre VARCHAR(60);
 DECLARE v_codigo INT;
 CALL sp_validar_comando(NEW.id_vehiculo,NEW.id_comando);
 SELECT nombre,codigo INTO v_nombre,v_codigo
 FROM comandos WHERE id_comando=NEW.id_comando;
 SET NEW.nombre_comando=v_nombre, NEW.codigo_comando=v_codigo;
END$$
CREATE TRIGGER tr_historial_actualizar BEFORE UPDATE ON historial_comandos FOR EACH ROW
BEGIN
 SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='El historial no se puede modificar';
END$$
CREATE TRIGGER tr_movimiento_insertar BEFORE INSERT ON demo_movimientos FOR EACH ROW
BEGIN
 CALL sp_validar_movimiento(NEW.id_demo,NEW.id_comando);
END$$
CREATE TRIGGER tr_movimiento_actualizar BEFORE UPDATE ON demo_movimientos FOR EACH ROW
BEGIN
 CALL sp_validar_movimiento(NEW.id_demo,NEW.id_comando);
END$$
DELIMITER ;

DELIMITER $$
CREATE PROCEDURE sp_crear_vehiculo(
    IN p_nombre VARCHAR(80),
    IN p_modelo VARCHAR(80),
    IN p_descripcion VARCHAR(255),
    IN p_microcontrolador VARCHAR(50)
)
BEGIN
    INSERT INTO vehiculos(nombre, modelo, descripcion, microcontrolador)
    VALUES(p_nombre, p_modelo, p_descripcion, p_microcontrolador);
    SELECT LAST_INSERT_ID() AS id_vehiculo;
END$$
CREATE PROCEDURE sp_obtener_vehiculos()
BEGIN
    SELECT * FROM vehiculos ORDER BY id_vehiculo;
END$$
CREATE PROCEDURE sp_obtener_vehiculo(IN p_id_vehiculo INT)
BEGIN
    SELECT * FROM vehiculos WHERE id_vehiculo = p_id_vehiculo;
END$$
CREATE PROCEDURE sp_actualizar_vehiculo(
    IN p_id_vehiculo INT,
    IN p_nombre VARCHAR(80),
    IN p_modelo VARCHAR(80),
    IN p_descripcion VARCHAR(255),
    IN p_microcontrolador VARCHAR(50),
    IN p_activo BOOLEAN
)
BEGIN
    UPDATE vehiculos
       SET nombre=p_nombre, modelo=p_modelo, descripcion=p_descripcion,
           microcontrolador=p_microcontrolador, activo=p_activo
     WHERE id_vehiculo=p_id_vehiculo;
END$$
CREATE PROCEDURE sp_eliminar_vehiculo(IN p_id_vehiculo INT)
BEGIN
    DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
    START TRANSACTION;
    -- Eliminar primero las demos evita conflictos con comandos usados en movimientos.
    DELETE FROM demos WHERE id_vehiculo=p_id_vehiculo;
    DELETE FROM vehiculos WHERE id_vehiculo=p_id_vehiculo;
    COMMIT;
END$$
CREATE PROCEDURE sp_crear_comando(
    IN p_id_vehiculo INT,
    IN p_nombre VARCHAR(60),
    IN p_codigo INT,
    IN p_descripcion VARCHAR(255)
)
BEGIN
    INSERT INTO comandos(id_vehiculo,nombre,codigo,descripcion)
    VALUES(p_id_vehiculo,p_nombre,p_codigo,p_descripcion);
    SELECT LAST_INSERT_ID() AS id_comando;
END$$
CREATE PROCEDURE sp_obtener_comandos_vehiculo(IN p_id_vehiculo INT)
BEGIN
    SELECT * FROM comandos
     WHERE id_vehiculo=p_id_vehiculo
     ORDER BY codigo;
END$$
CREATE PROCEDURE sp_actualizar_comando(
    IN p_id_comando INT,
    IN p_nombre VARCHAR(60),
    IN p_codigo INT,
    IN p_descripcion VARCHAR(255),
    IN p_activo BOOLEAN
)
BEGIN
    UPDATE comandos
       SET nombre=p_nombre, codigo=p_codigo,
           descripcion=p_descripcion, activo=p_activo
     WHERE id_comando=p_id_comando;
END$$
CREATE PROCEDURE sp_eliminar_comando(IN p_id_comando INT)
BEGIN
    DELETE FROM comandos WHERE id_comando=p_id_comando;
END$$
CREATE PROCEDURE sp_actualizar_estado(
    IN p_id_vehiculo INT,
    IN p_id_comando INT,
    IN p_conectado BOOLEAN
)
BEGIN
    INSERT INTO estado_vehiculo(id_vehiculo,id_comando,conectado)
    VALUES(p_id_vehiculo,p_id_comando,p_conectado)
    ON DUPLICATE KEY UPDATE
      id_comando=p_id_comando,
      conectado=p_conectado,
      fecha_actualizacion=CURRENT_TIMESTAMP;
END$$
CREATE PROCEDURE sp_obtener_estado(IN p_id_vehiculo INT)
BEGIN
    SELECT e.id_vehiculo, v.nombre AS vehiculo,
           e.id_comando, c.nombre AS comando, c.codigo,
           e.conectado, e.fecha_actualizacion
      FROM estado_vehiculo e
      JOIN vehiculos v ON v.id_vehiculo=e.id_vehiculo
 LEFT JOIN comandos c ON c.id_comando=e.id_comando
     WHERE e.id_vehiculo=p_id_vehiculo;
END$$
CREATE PROCEDURE sp_registrar_historial(
    IN p_id_vehiculo INT,
    IN p_id_comando INT,
    IN p_origen VARCHAR(30)
)
BEGIN
    INSERT INTO historial_comandos(id_vehiculo,id_comando,origen)
    VALUES(p_id_vehiculo,p_id_comando,p_origen);
END$$
CREATE PROCEDURE sp_obtener_historial(IN p_id_vehiculo INT)
BEGIN
    SELECT id_historial, id_vehiculo,
           nombre_comando AS comando,
           codigo_comando AS codigo,
           fecha_hora, origen
    FROM historial_comandos
    WHERE id_vehiculo = p_id_vehiculo
    ORDER BY fecha_hora DESC, id_historial DESC;
END$$
CREATE PROCEDURE sp_crear_demo(
    IN p_id_vehiculo INT,
    IN p_nombre VARCHAR(80),
    IN p_descripcion VARCHAR(255)
)
BEGIN
    INSERT INTO demos(id_vehiculo,nombre,descripcion)
    VALUES(p_id_vehiculo,p_nombre,p_descripcion);
    SELECT LAST_INSERT_ID() AS id_demo;
END$$
CREATE PROCEDURE sp_obtener_demos(IN p_id_vehiculo INT)
BEGIN
    SELECT * FROM demos
     WHERE id_vehiculo=p_id_vehiculo
     ORDER BY id_demo;
END$$
CREATE PROCEDURE sp_actualizar_demo(
    IN p_id_demo INT,
    IN p_nombre VARCHAR(80),
    IN p_descripcion VARCHAR(255),
    IN p_activo BOOLEAN
)
BEGIN
    UPDATE demos
       SET nombre=p_nombre, descripcion=p_descripcion, activo=p_activo
     WHERE id_demo=p_id_demo;
END$$
CREATE PROCEDURE sp_eliminar_demo(IN p_id_demo INT)
BEGIN
    DELETE FROM demos WHERE id_demo=p_id_demo;
END$$
CREATE PROCEDURE sp_agregar_movimiento_demo(
    IN p_id_demo INT,
    IN p_id_comando INT,
    IN p_orden INT,
    IN p_duracion_ms INT,
    IN p_pausa_ms INT
)
BEGIN
    IF p_orden IS NULL OR p_orden<=0 OR p_duracion_ms IS NULL OR p_duracion_ms<=0
       OR p_pausa_ms IS NULL OR p_pausa_ms<0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Orden y duracion deben ser positivos; pausa no negativa';
    END IF;
    INSERT INTO demo_movimientos
      (id_demo,id_comando,orden,duracion_ms,pausa_ms)
    VALUES
      (p_id_demo,p_id_comando,p_orden,p_duracion_ms,p_pausa_ms);
END$$
CREATE PROCEDURE sp_obtener_movimientos_demo(IN p_id_demo INT)
BEGIN
    SELECT dm.id_demo_movimiento, dm.orden,
           dm.id_comando, c.nombre AS comando, c.codigo,
           dm.duracion_ms, dm.pausa_ms
      FROM demo_movimientos dm
      JOIN comandos c ON c.id_comando=dm.id_comando
     WHERE dm.id_demo=p_id_demo
     ORDER BY dm.orden;
END$$
CREATE PROCEDURE sp_actualizar_movimiento_demo(
    IN p_id_demo_movimiento INT,
    IN p_id_comando INT,
    IN p_orden INT,
    IN p_duracion_ms INT,
    IN p_pausa_ms INT
)
BEGIN
    IF p_orden IS NULL OR p_orden<=0 OR p_duracion_ms IS NULL OR p_duracion_ms<=0
       OR p_pausa_ms IS NULL OR p_pausa_ms<0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='Orden y duracion deben ser positivos; pausa no negativa';
    END IF;
    UPDATE demo_movimientos
       SET id_comando=p_id_comando, orden=p_orden,
           duracion_ms=p_duracion_ms, pausa_ms=p_pausa_ms
     WHERE id_demo_movimiento=p_id_demo_movimiento;
END$$
CREATE PROCEDURE sp_eliminar_movimiento_demo(IN p_id_demo_movimiento INT)
BEGIN
    DELETE FROM demo_movimientos
     WHERE id_demo_movimiento=p_id_demo_movimiento;
END$$
DELIMITER ;

-- Usar este procedimiento para guardar estado e historial juntos.
-- Estos procedimientos administran su propia transaccion: llamarlos fuera de otra transaccion.
DELIMITER $$
CREATE PROCEDURE sp_registrar_comando(
 IN p_id_vehiculo INT, IN p_id_comando INT,
 IN p_conectado BOOLEAN, IN p_origen VARCHAR(30)
)
BEGIN
 DECLARE EXIT HANDLER FOR SQLEXCEPTION BEGIN ROLLBACK; RESIGNAL; END;
 START TRANSACTION;
 CALL sp_actualizar_estado(p_id_vehiculo,p_id_comando,p_conectado);
 CALL sp_registrar_historial(p_id_vehiculo,p_id_comando,p_origen);
 COMMIT;
END$$
DELIMITER ;
SHOW TABLES;
-- La base queda sin vehiculos, comandos ni demos de ejemplo.
-- Cada sp_crear_* devuelve el ID que debe guardar la aplicacion.
-- El historial registra solicitudes; no confirma ejecucion fisica en el ESP8266.

select * from vehiculos;
select * from comandos;