from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

from app.errors import AppError
from app.models.api import (
    VehiculoCrear, VehiculoActualizar, ComandoCrear, ComandoActualizar,
    EstadoActualizar, HistorialCrear, DemoCrear, DemoActualizar, PasoDemo, MovimientoCrear,
)

router = APIRouter()
Identificador = Annotated[int, Path(gt=0)]


def control(request: Request):
    return request.app.state.control


Control = Annotated[object, Depends(control)]


async def call(c, nombre, *args):
    return await c.db(c.repo.call, nombre, args)


async def obtener(c, tabla, identificador):
    return await c.db(c.repo.get, tabla, identificador)


async def modificar(c, vehiculo, nombre, *args, desconectado=False):
    async with c.locks[vehiculo]:
        c.libre(vehiculo)
        if desconectado and c.hub.conectado(vehiculo):
            raise AppError(409, "Desconecta la grua antes de modificarla o cambiar su catalogo")
        await call(c, nombre, *args)


async def validar_paso(c, vehiculo, datos):
    comando = await obtener(c, "comandos", datos.id_comando)
    if comando["id_vehiculo"] != vehiculo or not comando["activo"] or comando["codigo"] == 12:
        raise AppError(422, "El paso requiere un comando activo de esta grua distinto de 12")


@router.post("/vehiculos", tags=["Vehiculos"], status_code=201)
async def crear_vehiculo(datos: VehiculoCrear, c: Control):
    return (await call(c, "sp_crear_vehiculo", *datos.model_dump().values()))[0]


@router.get("/vehiculos", tags=["Vehiculos"])
async def vehiculos(c: Control):
    return await call(c, "sp_obtener_vehiculos")


@router.get("/vehiculos/{id}", tags=["Vehiculos"])
async def vehiculo(id: Identificador, c: Control):
    filas = await call(c, "sp_obtener_vehiculo", id)
    if not filas:
        raise AppError(404, "Vehiculo no encontrado")
    return filas[0]


@router.put("/vehiculos/{id}", tags=["Vehiculos"])
async def actualizar_vehiculo(id: Identificador, datos: VehiculoActualizar, c: Control):
    await obtener(c, "vehiculos", id)
    await modificar(c, id, "sp_actualizar_vehiculo", id, *datos.model_dump().values(), desconectado=not datos.activo)
    return await obtener(c, "vehiculos", id)


@router.delete("/vehiculos/{id}", tags=["Vehiculos"], status_code=204)
async def eliminar_vehiculo(id: Identificador, c: Control):
    await obtener(c, "vehiculos", id)
    await modificar(c, id, "sp_eliminar_vehiculo", id, desconectado=True)
    return Response(status_code=204)


@router.post("/vehiculos/{id}/comandos", tags=["Comandos"], status_code=201)
async def crear_comando(id: Identificador, datos: ComandoCrear, c: Control):
    await obtener(c, "vehiculos", id)
    async with c.locks[id]:
        c.libre(id)
        return (await call(c, "sp_crear_comando", id, *datos.model_dump().values()))[0]


@router.get("/vehiculos/{id}/comandos", tags=["Comandos"])
async def comandos(id: Identificador, c: Control):
    await obtener(c, "vehiculos", id)
    return await call(c, "sp_obtener_comandos_vehiculo", id)


@router.put("/comandos/{id}", tags=["Comandos"])
async def actualizar_comando(id: Identificador, datos: ComandoActualizar, c: Control):
    fila = await obtener(c, "comandos", id)
    await modificar(c, fila["id_vehiculo"], "sp_actualizar_comando", id, *datos.model_dump().values(), desconectado=True)
    return await obtener(c, "comandos", id)


@router.delete("/comandos/{id}", tags=["Comandos"], status_code=204)
async def eliminar_comando(id: Identificador, c: Control):
    fila = await obtener(c, "comandos", id)
    await modificar(c, fila["id_vehiculo"], "sp_eliminar_comando", id, desconectado=True)
    return Response(status_code=204)


@router.put("/vehiculos/{id}/estado", tags=["Estado"])
async def actualizar_estado(id: Identificador, datos: EstadoActualizar, c: Control):
    await obtener(c, "vehiculos", id)
    async with c.locks[id]:
        c.libre(id)
        await call(c, "sp_actualizar_estado", id, datos.id_comando, c.hub.conectado(id))
    return await c.db(c.repo.estado, id)


@router.get("/vehiculos/{id}/estado", tags=["Estado"])
async def estado(id: Identificador, c: Control):
    fila = await c.db(c.repo.estado, id)
    # La presencia en esta instancia es la fuente del estado de conexion actual.
    return {**fila, "conectado": c.hub.conectado(id)}


@router.post("/vehiculos/{id}/historial", tags=["Historial"], status_code=201)
async def registrar_historial(id: Identificador, datos: HistorialCrear, c: Control):
    await call(c, "sp_registrar_historial", id, datos.id_comando, datos.origen)
    return {"registrado": True, "id_vehiculo": id, "id_comando": datos.id_comando}


@router.get("/vehiculos/{id}/historial", tags=["Historial"])
async def historial(id: Identificador, c: Control):
    await obtener(c, "vehiculos", id)
    return await call(c, "sp_obtener_historial", id)


@router.post("/vehiculos/{id}/demos", tags=["Demos"], status_code=201)
async def crear_demo(id: Identificador, datos: DemoCrear, c: Control):
    await obtener(c, "vehiculos", id)
    return (await call(c, "sp_crear_demo", id, *datos.model_dump().values()))[0]


@router.get("/vehiculos/{id}/demos", tags=["Demos"])
async def demos(id: Identificador, c: Control):
    await obtener(c, "vehiculos", id)
    return await call(c, "sp_obtener_demos", id)


@router.put("/demos/{id}", tags=["Demos"])
async def actualizar_demo(id: Identificador, datos: DemoActualizar, c: Control):
    fila = await obtener(c, "demos", id)
    await modificar(c, fila["id_vehiculo"], "sp_actualizar_demo", id, *datos.model_dump().values())
    return await obtener(c, "demos", id)


@router.delete("/demos/{id}", tags=["Demos"], status_code=204)
async def eliminar_demo(id: Identificador, c: Control):
    fila = await obtener(c, "demos", id)
    await modificar(c, fila["id_vehiculo"], "sp_eliminar_demo", id)
    return Response(status_code=204)


@router.post("/demos/{id}/movimientos", tags=["Pasos de demos"], status_code=201)
async def agregar_paso(id: Identificador, datos: PasoDemo, c: Control):
    demo = await obtener(c, "demos", id)
    await validar_paso(c, demo["id_vehiculo"], datos)
    await modificar(c, demo["id_vehiculo"], "sp_agregar_movimiento_demo", id, *datos.model_dump().values())
    return {"registrado": True, "id_demo": id, **datos.model_dump()}


@router.get("/demos/{id}/movimientos", tags=["Pasos de demos"])
async def pasos(id: Identificador, c: Control):
    await obtener(c, "demos", id)
    return await call(c, "sp_obtener_movimientos_demo", id)


@router.put("/movimientos-demo/{id}", tags=["Pasos de demos"])
async def actualizar_paso(id: Identificador, datos: PasoDemo, c: Control):
    fila = await obtener(c, "demo_movimientos", id)
    demo = await obtener(c, "demos", fila["id_demo"])
    await validar_paso(c, demo["id_vehiculo"], datos)
    await modificar(c, demo["id_vehiculo"], "sp_actualizar_movimiento_demo", id, *datos.model_dump().values())
    return await obtener(c, "demo_movimientos", id)


@router.delete("/movimientos-demo/{id}", tags=["Pasos de demos"], status_code=204)
async def eliminar_paso(id: Identificador, c: Control):
    fila = await obtener(c, "demo_movimientos", id)
    demo = await obtener(c, "demos", fila["id_demo"])
    await modificar(c, demo["id_vehiculo"], "sp_eliminar_movimiento_demo", id)
    return Response(status_code=204)


@router.post("/vehiculos/{id}/movimientos", tags=["Control"])
async def registrar_movimiento(id: Identificador, datos: MovimientoCrear, c: Control):
    return await c.movimiento(id, datos)
