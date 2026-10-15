from pydantic import BaseModel, Field


class Estado(BaseModel):

    status: int = Field(strict=True, ge=1, le=12)
