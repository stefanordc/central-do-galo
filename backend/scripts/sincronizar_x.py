import argparse
import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.pool import close_pool, open_pool
from app.services.x_scrape_service import XScrapeService
from app.services.x_service import listar_contas_x
from app.services.x_sync_service import XSyncService


def configurar_logs() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _normalizar_contas(valor: str | None) -> list[str]:
    if not valor:
        return []
    return [item.strip().lstrip("@") for item in valor.split(",") if item.strip()]


def _fonte(settings) -> str:
    return (
        "x_api_v2"
        if (settings.x_source or "scrape").strip().lower() in {"x_api_v2", "api", "official"}
        else "x_seleniumbase_uc_scrape"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincroniza posts do X no Central do Galo")
    parser.add_argument("--conta", help="Sincroniza somente uma conta, ex.: --conta Atletico")
    parser.add_argument(
        "--contas",
        help="Sincroniza várias contas separadas por vírgula",
    )
    args = parser.parse_args()
    if args.conta and args.contas:
        parser.error("Use --conta ou --contas, não os dois.")

    configurar_logs()
    logger = logging.getLogger("central_galo.x_job")
    settings = get_settings()
    source = _fonte(settings)
    solicitadas = [args.conta.lstrip("@")] if args.conta else _normalizar_contas(args.contas)

    print("\n=== CENTRAL DO GALO | SINCRONIZAÇÃO DO X ===")
    print(f"Fonte: {'x.com via SeleniumBase UC + oEmbed' if source == 'x_seleniumbase_uc_scrape' else 'X API v2'}")
    print("Embed: publish.x.com/oembed")
    print("Escopo: " + (", ".join(f"@{item}" for item in solicitadas) if solicitadas else "todas as contas ativas"))

    open_pool()
    service = None
    try:
        cadastradas = listar_contas_x()
        if solicitadas:
            alvo = {item.lower() for item in solicitadas}
            contas = [item for item in cadastradas if item["usuario"].lower() in alvo]
        else:
            contas = cadastradas

        print(f"Contas ativas encontradas no Supabase: {len(contas)}")
        for conta in contas:
            logger.info(
                "[preflight] @%s cadastrada=SIM ativa=SIM status=%s",
                conta["usuario"],
                conta.get("status_sync") or "-",
            )

        if solicitadas:
            encontradas = {item["usuario"].lower() for item in contas}
            ausentes = [item for item in solicitadas if item.lower() not in encontradas]
            for usuario in ausentes:
                logger.error("[preflight] @%s cadastrada=NAO/INATIVA", usuario)
            if ausentes:
                return 3

        if source == "x_api_v2":
            if not (settings.x_bearer_token or "").strip():
                print("ERRO: X_SOURCE=x_api_v2, mas X_BEARER_TOKEN não está configurado.")
                return 2
            service = XSyncService()
        else:
            service = XScrapeService()

        resultados: list[dict] = []
        if solicitadas:
            for usuario in solicitadas:
                logger.info("[job] tentativa explícita para @%s", usuario)
                parcial = service.sincronizar_todas(usuario=usuario)
                resultados.extend(parcial["resultados"])
        else:
            resultados = service.sincronizar_todas()["resultados"]

        print("\n--- RESULTADO ---")
        for item in resultados:
            print(
                f"@{item['usuario']}: novos={item['novos']} | "
                f"embeds={item['embeds_atualizados']} | status={item['status']}"
                + (f" | erro={item['erro']}" if item.get("erro") else "")
            )
        total_novos = sum(item["novos"] for item in resultados)
        total_embeds = sum(item["embeds_atualizados"] for item in resultados)
        print(f"TOTAL: contas={len(resultados)} | novos={total_novos} | embeds={total_embeds}")
        return 1 if any(item["status"] != "ok" for item in resultados) else 0
    except Exception as exc:
        logger.exception("Falha geral do job: %s", exc)
        print(f"ERRO GERAL: {exc}")
        return 1
    finally:
        if service is not None:
            service.close()
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
