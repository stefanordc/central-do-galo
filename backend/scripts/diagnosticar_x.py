import logging
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.db.pool import close_pool, open_pool
from app.services.x_scrape_service import XScrapeService
from app.services.x_service import listar_contas_x, obter_status_x
from app.services.x_sync_service import XSyncService

CONTAS_VALIDACAO = [
    "Atletico",
    "pedfaria",
    "ohenriqueandre",
    "Igortep",
    "GaloCareca21",
    "InfoGalo_",
]


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    settings = get_settings()
    source = (
        "x_api_v2"
        if (settings.x_source or "scrape").strip().lower() in {"x_api_v2", "api", "official"}
        else "x_seleniumbase_uc_scrape"
    )

    print("=== DIAGNÓSTICO RADAR DO X ===")
    print(f"Fonte configurada: {source}")
    print("oEmbed: https://publish.x.com/oembed")
    print(f"Job interno habilitado: {'SIM' if settings.x_sync_enabled else 'NÃO'}")
    if source == "x_seleniumbase_uc_scrape":
        print("Coleta: x.com via SeleniumBase UC, sem login")
        print("Parser principal: DOM vivo por links /<usuario>/status/<id>")
        print(f"Headless: {'SIM' if settings.x_scrape_headless else 'NÃO'}")
        print(f"Intervalo: {settings.x_scrape_interval_seconds}s")
        print(f"Intervalo entre contas: {settings.x_scrape_delay_between_accounts_seconds}s")
        print(f"Espera máxima da timeline: {settings.x_scrape_timeline_wait_seconds}s")
        print(f"Debug de falha: {'SIM' if settings.x_scrape_debug_enabled else 'NÃO'} | pasta={settings.x_scrape_debug_dir}")
    else:
        print(f"X_BEARER_TOKEN configurado: {'SIM' if (settings.x_bearer_token or '').strip() else 'NÃO'}")

    open_pool()
    service = None
    try:
        status = obter_status_x()
        print(
            "Supabase: "
            f"contas={status['contas_ativas']} | nunca_sincronizadas={status['nunca_sincronizadas']} | "
            f"posts={status['posts_total']} | embeds_ok={status['embeds_ok']} | embeds_erro={status['embeds_erro']}"
        )
        contas = listar_contas_x()
        por_usuario = {item["usuario"].lower(): item for item in contas}

        print("\n--- CONTAS DA VALIDAÇÃO ---")
        faltando = False
        for usuario in CONTAS_VALIDACAO:
            conta = por_usuario.get(usuario.lower())
            if conta is None:
                faltando = True
                print(f"@{usuario}: CADASTRADA=NAO/INATIVA")
                continue
            print(
                f"@{conta['usuario']}: CADASTRADA=SIM | ativa={conta['ativo']} | "
                f"status={conta.get('status_sync') or '-'} | ultima_sync={conta.get('ultima_sincronizacao') or '-'}"
                + (f" | erro={conta.get('sync_erro')}" if conta.get("sync_erro") else "")
            )
        if faltando:
            return 3

        if source == "x_api_v2":
            if not (settings.x_bearer_token or "").strip():
                print("DIAGNÓSTICO: X API selecionada, mas Bearer Token ausente.")
                return 2
            service = XSyncService()
        else:
            service = XScrapeService()

        print("\nTeste ponta a ponta: sincronizando somente @Atletico...")
        resultado = service.sincronizar_todas(usuario="Atletico")
        item = resultado["resultados"][0]
        print(
            f"@Atletico: status={item['status']} | novos={item['novos']} | embeds={item['embeds_atualizados']}"
            + (f" | erro={item['erro']}" if item.get("erro") else "")
        )
        status_depois = obter_status_x()
        print(
            "Supabase após @Atletico: "
            f"posts={status_depois['posts_total']} | embeds_ok={status_depois['embeds_ok']}"
        )
        if item["status"] != "ok" or status_depois["embeds_ok"] <= 0:
            print("VALIDAÇÃO INTERROMPIDA: @Atletico ainda não produziu embed real.")
            return 1

        print("\n@Atletico OK. Validando as outras 5 contas...")
        falhas = 0
        for usuario in CONTAS_VALIDACAO[1:]:
            parcial = service.sincronizar_todas(usuario=usuario)
            conta_result = parcial["resultados"][0]
            print(
                f"@{usuario}: status={conta_result['status']} | novos={conta_result['novos']} | "
                f"embeds={conta_result['embeds_atualizados']}"
                + (f" | erro={conta_result['erro']}" if conta_result.get("erro") else "")
            )
            falhas += int(conta_result["status"] != "ok")
        return 1 if falhas else 0
    finally:
        if service is not None:
            service.close()
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
