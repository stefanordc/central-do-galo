from fastapi import APIRouter, Query

from app.services.video_service import (
    listar_feed_videos_cacheado,
    listar_videos,
    status_videos,
)

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("")
def get_videos(
    tipo: str | None = Query(default=None, pattern="^(video|short|live)$"),
    limit: int = Query(default=10, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    fonte: str | None = Query(default=None, max_length=120),
) -> list[dict]:
    return listar_videos(
        tipo=tipo,
        limit=limit,
        offset=offset,
        fonte=fonte.strip() if fonte else None,
    )


@router.get("/feed")
def get_video_feed(
    limit_por_canal: int = Query(default=13, ge=1, le=50),
) -> dict:
    return listar_feed_videos_cacheado(
        limit_por_canal=limit_por_canal,
    )


@router.get("/status")
def get_video_status() -> dict:
    return status_videos()
