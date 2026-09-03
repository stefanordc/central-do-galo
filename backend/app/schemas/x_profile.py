from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ContaXOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    usuario: str
    oficial: bool
    confiabilidade: int = Field(ge=0, le=100)
    ativo: bool
