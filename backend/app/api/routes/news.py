from fastapi import APIRouter, Query

from app.schemas.news import NoticiaOut
from app.services.news_service import listar_noticias

router = APIRouter(prefix="/noticias", tags=["noticias"])


@router.get("", response_model=list[NoticiaOut])
def get_noticias(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    categoria: str | None = Query(default=None),
    fonte: str | None = Query(default=None),
    q: str | None = Query(default=None, min_length=2, max_length=120),
) -> list[dict]:
    return listar_noticias(
        limit=limit,
        offset=offset,
        categoria=categoria,
        fonte=fonte,
        busca=q.strip() if q else None,
    )
