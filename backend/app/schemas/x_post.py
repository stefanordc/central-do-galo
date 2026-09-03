from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PostXOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    post_id: str
    url: str
    texto: str | None = None
    publicado_em: datetime | None = None
    coletado_em: datetime
    metricas: dict = Field(default_factory=dict)
    midia: list[dict] = Field(default_factory=list)
    embed_html: str | None = None
    embed_status: str
    embed_atualizado_em: datetime | None = None


class ContaXComPostsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nome: str
    usuario: str
    foto_url: str | None = None
    oficial: bool
    confiabilidade: int = Field(ge=0, le=100)
    ultima_sincronizacao: datetime | None = None
    status_sync: str
    sync_erro: str | None = None
    posts: list[PostXOut] = Field(default_factory=list)


class PostXFeedOut(PostXOut):
    conta_id: UUID
    conta_nome: str
    conta_usuario: str
    conta_foto_url: str | None = None
    conta_oficial: bool


class XSyncContaResultado(BaseModel):
    usuario: str
    novos: int = 0
    embeds_atualizados: int = 0
    status: str
    erro: str | None = None


class XSyncResultado(BaseModel):
    contas: int
    novos: int
    embeds_atualizados: int
    resultados: list[XSyncContaResultado]
