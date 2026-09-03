from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ArticleCandidate:
    titulo: str
    url: str
    publicado_em: datetime | None = None
    descoberta_por: str = "listing"
    resumo: str | None = None
    imagem_url: str | None = None


@dataclass(slots=True)
class ArticleMetadata:
    titulo: str
    url: str
    resumo: str | None = None
    imagem_url: str | None = None
    categoria: str | None = None
    publicado_em: datetime | None = None
    metadados: dict = field(default_factory=dict)
