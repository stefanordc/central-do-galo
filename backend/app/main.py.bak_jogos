import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.categories import router as categories_router
from app.api.routes.health import router as health_router
from app.api.routes.news import router as news_router
from app.api.routes.pages import router as pages_router
from app.api.routes.sources import router as sources_router
from app.api.routes.x_profiles import router as x_router
from app.api.routes.videos import router as videos_router
from app.collectors.runner import NewsCollectorRunner
from app.core.config import get_settings
from app.db.pool import close_pool, open_pool
from app.services.x_scrape_service import XScrapeService
from app.services.x_sync_service import XSyncService
from app.services.video_service import sincronizar_youtube

settings = get_settings()
logger = logging.getLogger("central_galo")
logger.setLevel(logging.INFO)


def _x_source() -> str:
    source = (settings.x_source or "scrape").strip().lower()
    if source in {"scrape", "x_public_scrape", "public_scrape"}:
        return "scrape"
    if source in {"x_api_v2", "api", "official"}:
        return "x_api_v2"
    logger.warning("[Radar do X] X_SOURCE=%r desconhecido; usando scrape", settings.x_source)
    return "scrape"


def _x_interval() -> int:
    return (
        settings.x_scrape_interval_seconds
        if _x_source() == "scrape"
        else settings.x_sync_interval_seconds
    )


def _x_initial_delay() -> int:
    return (
        settings.x_scrape_initial_delay_seconds
        if _x_source() == "scrape"
        else settings.x_sync_initial_delay_seconds
    )


def _run_x_once() -> dict:
    if _x_source() == "scrape":
        service = XScrapeService()
    else:
        service = XSyncService()
    try:
        return service.sincronizar_todas()
    finally:
        service.close()


async def news_collector_loop() -> None:
    await asyncio.sleep(settings.news_collection_initial_delay_seconds)

    while True:
        try:
            runner = NewsCollectorRunner(
                delay_seconds=settings.news_collection_request_delay_seconds
            )
            results = await asyncio.to_thread(runner.collect_all)

            print("\n=== CENTRAL DO GALO | COLETA AUTOMÁTICA ===")
            for result in results:
                print(
                    f"{result.fonte}: "
                    f"candidatos={result.candidatos} | "
                    f"novos={result.novos_encontrados} | "
                    f"inseridos={result.inseridos} | "
                    f"enriquecidos={result.enriquecidos} | "
                    f"paginas={result.paginas_lidas} | "
                    f"robots={result.ignorados_robots} | "
                    f"erros={result.erros} | "
                    f"status={result.mensagem}"
                )
            print("============================================\n")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("[notícias] erro geral da coleta automática: %s", exc)

        await asyncio.sleep(settings.news_collection_interval_seconds)


async def youtube_sync_loop() -> None:
    await asyncio.sleep(settings.youtube_sync_initial_delay_seconds)

    while True:
        try:
            logger.info("[YouTube] iniciando sincronização automática")
            resultado = await asyncio.to_thread(sincronizar_youtube)
            erros = sum(len(item.get("erros", [])) for item in resultado.get("resultados", []))
            logger.info(
                "[YouTube] concluído: fontes=%s processados=%s salvos=%s erros=%s",
                resultado.get("fontes", 0),
                resultado.get("processados", 0),
                resultado.get("salvos", 0),
                erros,
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("[YouTube] erro geral da sincronização automática: %s", exc)

        await asyncio.sleep(settings.youtube_sync_interval_seconds)


async def x_sync_loop() -> None:
    await asyncio.sleep(_x_initial_delay())

    while True:
        try:
            fonte = "x.com SeleniumBase UC público + oEmbed" if _x_source() == "scrape" else "X API v2"
            logger.info("[Radar do X] iniciando sincronização automática | fonte=%s", fonte)
            resultado = await asyncio.to_thread(_run_x_once)
            erros = [item for item in resultado["resultados"] if item["status"] != "ok"]
            logger.info(
                "[Radar do X] concluído: contas=%s novos=%s embeds=%s erros=%s",
                resultado["contas"],
                resultado["novos"],
                resultado["embeds_atualizados"],
                len(erros),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("[Radar do X] erro geral da sincronização automática: %s", exc)

        await asyncio.sleep(_x_interval())


@asynccontextmanager
async def lifespan(_: FastAPI):
    open_pool()

    collector_task: asyncio.Task | None = None
    if settings.news_collection_enabled:
        collector_task = asyncio.create_task(news_collector_loop())

    youtube_task: asyncio.Task | None = None
    if settings.youtube_sync_enabled:
        logger.info(
            "[YouTube] job automático habilitado | intervalo=%ss | itens por seção=%s",
            settings.youtube_sync_interval_seconds,
            settings.youtube_items_per_section,
        )
        youtube_task = asyncio.create_task(youtube_sync_loop())

    x_task: asyncio.Task | None = None
    if settings.x_sync_enabled:
        if _x_source() == "x_api_v2" and not (settings.x_bearer_token or "").strip():
            logger.error(
                "[Radar do X] X_SOURCE=x_api_v2, mas X_BEARER_TOKEN não está configurado. "
                "O job oficial não foi iniciado."
            )
        else:
            logger.warning(
                "[Radar do X] fonte=%s | intervalo=%ss | SeleniumBase UC headless; sem login.",
                "x_seleniumbase_uc_scrape" if _x_source() == "scrape" else "x_api_v2",
                _x_interval(),
            )
            x_task = asyncio.create_task(x_sync_loop())
    else:
        logger.info("[Radar do X] job automático desabilitado; use sincronização manual/n8n.")

    yield

    for task in (collector_task, youtube_task, x_task):
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    close_pool()


app = FastAPI(
    title=settings.app_name,
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(pages_router, prefix="/api")
app.include_router(categories_router, prefix="/api")
app.include_router(news_router, prefix="/api")
app.include_router(sources_router, prefix="/api")
app.include_router(x_router, prefix="/api")
app.include_router(videos_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "projeto": "Central do Galo",
        "api": "online",
        "coleta_automatica": settings.news_collection_enabled,
        "intervalo_segundos": settings.news_collection_interval_seconds,
        "youtube": {
            "job_habilitado": settings.youtube_sync_enabled,
            "intervalo_segundos": settings.youtube_sync_interval_seconds,
            "itens_por_secao": settings.youtube_items_per_section,
        },
        "radar_x": {
            "fonte": "x_seleniumbase_uc_scrape" if _x_source() == "scrape" else "x_api_v2",
            "job_habilitado": settings.x_sync_enabled,
            "token_configurado": bool((settings.x_bearer_token or "").strip()),
            "intervalo_segundos": _x_interval(),
            "headless": settings.x_scrape_headless if _x_source() == "scrape" else None,
            "descoberta": "x.com via SeleniumBase UC" if _x_source() == "scrape" else "api.x.com",
        },
        "docs": "/docs",
    }
