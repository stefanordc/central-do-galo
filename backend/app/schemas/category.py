from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CategoriaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    slug: str
    descricao: str | None = None
    ordem: int
    total_noticias: int = 0


class CategoriaResumo(BaseModel):
    nome: str
    slug: str
    principal: bool
