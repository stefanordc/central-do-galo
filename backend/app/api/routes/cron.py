import secrets

from fastapi import APIRouter, Header, HTTPException, status

from app.collectors.runner import NewsCollectorRunner
from app.core.config import get_settings
from app.services.video_service import sincronizar_youtube
from app.services.x_scrape_service import XScrapeService
from app.services.x_sync_service import XSyncService

router = APIRouter(prefix="/cron", tags=["cron"])
settings = get_settings()


def _validar_cron(authorization: str | None) -> None:
    segredo = (settings.cron_secret or "").strip()
    if not segredo:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CRON_SECRET não configurado.",
        )

    esperado = f"Bearer {segredo}"
    if not authorization or not secrets.compare_digest(authorization, esperado):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cron não autorizado.",
        )


@router.get("/noticias")
def cron_noticias(
    authorization: str | None = Header(default=None),
) -> dict:
    _validar_cron(authorization)

    runner = NewsCollectorRunner(
        delay_seconds=settings.news_collection_request_delay_seconds
    )
    resultados = runner.collect_all()

    return {
        "ok": True,
        "tipo": "noticias",
        "fontes": len(resultados),
        "inseridos": sum(item.inseridos for item in resultados),
        "erros": sum(item.erros for item in resultados),
    }


@router.get("/youtube")
def cron_youtube(
    authorization: str | None = Header(default=None),
) -> dict:
    _validar_cron(authorization)
    resultado = sincronizar_youtube()
    return {
        "ok": True,
        "tipo": "youtube",
        "resultado": resultado,
    }


@router.get("/x")
def cron_x(
    authorization: str | None = Header(default=None),
) -> dict:
    _validar_cron(authorization)

    source = (settings.x_source or "scrape").strip().lower()
    if source in {"x_api_v2", "api", "official"}:
        service = XSyncService()
    else:
        service = XScrapeService()

    try:
        resultado = service.sincronizar_todas()
    finally:
        service.close()

    return {
        "ok": True,
        "tipo": "x",
        "resultado": resultado,
    }
