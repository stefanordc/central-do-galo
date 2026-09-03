from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.category import CategoriaResumo


class NoticiaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    titulo: str
    url: str
    resumo: str | None = None
    imagem_url: str | None = None
    categoria: str | None = None
    categorias: list[CategoriaResumo] = Field(default_factory=list)
    oficial: bool
    publicado_em: datetime | None = None
    coletado_em: datetime
    fonte_id: UUID
    fonte_nome: str
    fonte_slug: str
    fonte_confiabilidade: int = Field(ge=0, le=100)
