from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FonteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    slug: str
    tipo: str
    url_base: str | None = None
    url_feed: str | None = None
    confiabilidade: int = Field(ge=0, le=100)
    oficial: bool
    ativo: bool
