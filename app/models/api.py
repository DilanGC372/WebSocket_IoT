from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[int, Field(strict=True, gt=0)]
Codigo = Annotated[int, Field(strict=True, ge=1, le=12)]
Nombre = Annotated[str, Field(min_length=1, max_length=80)]


class Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class VehiculoCrear(Entrada):
    nombre: Nombre
    modelo: str | None = Field(default=None, max_length=80)
    descripcion: str | None = Field(default=None, max_length=255)
    microcontrolador: str | None = Field(default=None, max_length=50)


class VehiculoActualizar(VehiculoCrear):
    activo: bool = Field(strict=True)


class ComandoCrear(Entrada):
    nombre: str = Field(min_length=1, max_length=60)
    codigo: Codigo
    descripcion: str | None = Field(default=None, max_length=255)


class ComandoActualizar(ComandoCrear):
    activo: bool = Field(strict=True)


class EstadoActualizar(Entrada):
    id_comando: Id | None = None


class HistorialCrear(Entrada):
    id_comando: Id
    origen: str = Field(default="MANUAL", min_length=1, max_length=30)


class DemoCrear(Entrada):
    nombre: Nombre
    descripcion: str | None = Field(default=None, max_length=255)


class DemoActualizar(DemoCrear):
    activo: bool = Field(strict=True)


class PasoDemo(Entrada):
    id_comando: Id
    orden: int = Field(strict=True, gt=0, le=2147483647)
    duracion_ms: int = Field(strict=True, gt=0, le=2147483647)
    pausa_ms: int = Field(default=0, strict=True, ge=0, le=2147483647)


class MovimientoCrear(Entrada):
    codigo: Codigo
    origen: str = Field(default="MANUAL", min_length=1, max_length=30)
    id_demo: Id | None = None

    @model_validator(mode="after")
    def validar_demo(self):
        if (self.codigo == 12) != (self.id_demo is not None):
            raise ValueError("El codigo 12 requiere id_demo; los demas no lo aceptan")
        return self


class ControlDemo(Entrada):
    accion: Literal["iniciar", "cancelar"]
    id_demo: Id | None = None

    @model_validator(mode="after")
    def validar_accion(self):
        if (self.accion == "iniciar") != (self.id_demo is not None):
            raise ValueError("iniciar requiere id_demo; cancelar no lo acepta")
        return self


class Confirmacion(Entrada):
    evento: Literal["confirmacion"]
    id_orden: str = Field(min_length=1, max_length=36)
    resultado: Literal["recibido", "ejecutado", "error"]
