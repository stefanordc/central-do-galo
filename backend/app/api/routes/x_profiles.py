import secrets
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Response

from app.core.config import get_settings
from app.schemas.x_post import ContaXComPostsOut, PostXFeedOut, XSyncResultado
from app.schemas.x_profile import ContaXOut
from app.services.x_scrape_service import XScrapeService
from app.services.x_service import (
    listar_contas_x,
    listar_feed_x,
    listar_posts_x_agrupados,
    obter_status_x,
)
from app.services.x_sync_service import XSyncService

router = APIRouter(prefix="/x", tags=["x"])
settings = get_settings()


def _source() -> str:
    source = (settings.x_source or "scrape").strip().lower()
    return "x_api_v2" if source in {"x_api_v2", "api", "official"} else "x_seleniumbase_uc_scrape"


def _intervalo() -> int:
    return (
        settings.x_sync_interval_seconds
        if _source() == "x_api_v2"
        else settings.x_scrape_interval_seconds
    )


@router.get("/contas", response_model=list[ContaXOut])
def get_contas_x() -> list[dict]:
    return listar_contas_x()


@router.get("/posts", response_model=list[ContaXComPostsOut])
def get_posts_x(
    limit_por_conta: int = Query(default=3, ge=1, le=10),
) -> list[dict]:
    return listar_posts_x_agrupados(limit_por_conta=limit_por_conta)


@router.get("/status")
def get_status_x() -> dict:
    status = obter_status_x()
    source = _source()
    status.update(
        {
            "fonte": source,
            "oembed": "publish.x.com/oembed",
            "token_configurado": bool((settings.x_bearer_token or "").strip()),
            "scraping_habilitado": source == "x_seleniumbase_uc_scrape",
            "scraping_perfil_chrome": None,
            "job_backend_habilitado": settings.x_sync_enabled,
            "intervalo_segundos": _intervalo(),
        }
    )
    return status


@router.get("/feed", response_model=list[PostXFeedOut])
def get_feed_x(
    limit: int = Query(default=60, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    usuario: str | None = Query(default=None, min_length=1, max_length=50),
) -> list[dict]:
    return listar_feed_x(limit=limit, offset=offset, usuario=usuario)




@router.get("/media")
def get_x_media(url: str = Query(..., min_length=10, max_length=2000)) -> Response:
    """Proxy restrito para imagens públicas do CDN do X.

    Mantém o navegador falando apenas com localhost e evita que bloqueadores
    do cliente impeçam a exibição de pbs.twimg.com. O host e os paths aceitos
    são rigidamente validados para não transformar a rota em proxy aberto.
    """
    try:
        parsed = urlsplit(url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="URL de mídia inválida.") from exc

    if parsed.scheme != "https" or parsed.hostname != "pbs.twimg.com":
        raise HTTPException(status_code=400, detail="Host de mídia não permitido.")

    path = parsed.path.lower()
    allowed_paths = (
        "/media/",
        "/ext_tw_video_thumb/",
        "/amplify_video_thumb/",
        "/tweet_video_thumb/",
    )
    if not any(piece in path for piece in allowed_paths):
        raise HTTPException(status_code=400, detail="Path de mídia não permitido.")

    try:
        with httpx.Client(
            timeout=15.0,
            follow_redirects=True,
            headers={
                "User-Agent": settings.x_scrape_user_agent or (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/151.0.0.0 Safari/537.36"
                ),
                "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
                "Referer": "https://x.com/",
            },
        ) as client:
            upstream = client.get(url)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Falha ao carregar mídia do X.") from exc

    if not upstream.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"CDN do X respondeu HTTP {upstream.status_code}.",
        )

    content_type = (upstream.headers.get("content-type") or "image/jpeg").split(";", 1)[0]
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="Conteúdo retornado não é uma imagem.")

    return Response(
        content=upstream.content,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
        },
    )

@router.post("/sync", response_model=XSyncResultado)
def sincronizar_x(
    conta: str | None = Query(default=None),
    x_sync_secret: str | None = Header(default=None, alias="X-Sync-Secret"),
) -> dict:
    segredo_configurado = (settings.x_sync_secret or "").strip()
    if not segredo_configurado:
        raise HTTPException(
            status_code=503,
            detail="X_SYNC_SECRET não configurado no backend.",
        )

    if not x_sync_secret or not secrets.compare_digest(
        x_sync_secret, segredo_configurado
    ):
        raise HTTPException(status_code=401, detail="Segredo de sincronização inválido.")

    source = _source()
    if source == "x_api_v2":
        if not (settings.x_bearer_token or "").strip():
            raise HTTPException(
                status_code=503,
                detail="X_BEARER_TOKEN não configurado no backend.",
            )
        service = XSyncService()
    else:
        service = XScrapeService()

    try:
        return service.sincronizar_todas(usuario=conta)
    finally:
        service.close()
