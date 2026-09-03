from fastapi import APIRouter, Query

from app.services.video_service import listar_videos, status_videos

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


@router.get("/status")
def get_video_status() -> dict:
    return status_videos()
