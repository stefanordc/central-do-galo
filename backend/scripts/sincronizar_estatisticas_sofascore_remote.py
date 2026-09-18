from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.data_collector_store import remote_call
from app.services.jogo_service import _sofascore_get, fechar_cliente_sofascore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("central_galo.dados.remote")

def _fetch_widget_lineups(event_id: int, tentativas: int = 3) -> dict:
    url = f"https://widgets.sofascore.com/embed/lineups?id={event_id}"
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]

    for tentativa in range(1, tentativas + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
                "Accept-Encoding": "identity",
                "Referer": "https://www.sofascore.com/",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                html = response.read().decode("utf-8", errors="replace")

            match = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                html,
                re.DOTALL,
            )
            if not match:
                raise RuntimeError("Widget sem __NEXT_DATA__.")

            data = json.loads(match.group(1))
            page_props = data.get("props", {}).get("pageProps", {})
            lineups = page_props.get("initialLineups") or {}

            if isinstance(lineups, dict) and ("home" in lineups or "away" in lineups):
                return lineups

            raise RuntimeError("Widget sem initialLineups.")
        except Exception as exc:
            if tentativa >= tentativas:
                raise RuntimeError(
                    f"Falha no widget de lineups do evento {event_id}: {exc}"
                ) from exc
            time.sleep(1.5 * tentativa + random.uniform(0.2, 0.8))

    return {}



def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza estatísticas coletivas e individuais via GitHub Actions."
    )
    parser.add_argument("--ano", type=int, default=datetime.now().year)
    parser.add_argument("--recent-days", type=int, default=4)
    args = parser.parse_args()

    jogos_resp = remote_call(
        "list_games",
        temporada=args.ano,
        recent_days=args.recent_days,
    )
    jogos = jogos_resp.get("data") or []

    logger.info("[Dados] %s jogo(s) pendente(s)/recente(s)", len(jogos))

    processados = 0
    jogadores_salvos = 0
    erros: list[str] = []

    try:
        for idx, jogo in enumerate(jogos, 1):
            event_id = int(jogo["event_id"])
            lado = str(jogo["lado_galo"])
            logger.info(
                "[Dados] %s/%s event=%s %s x %s",
                idx,
                len(jogos),
                event_id,
                jogo.get("mandante"),
                jogo.get("visitante"),
            )

            try:
                estatisticas = _sofascore_get(f"/event/{event_id}/statistics")
                lineups = _fetch_widget_lineups(event_id)

                logger.info(
                    "[Dados] widget lineups home_players=%s away_players=%s",
                    len((lineups.get("home") or {}).get("players") or []),
                    len((lineups.get("away") or {}).get("players") or []),
                )

                result = remote_call(
                    "save_game",
                    jogo_id=str(jogo["id"]),
                    event_id=event_id,
                    lado_galo=lado,
                    estatisticas=estatisticas,
                    lineups=lineups,
                )

                processados += 1
                jogadores_salvos += int(result.get("jogadores_salvos") or 0)
            except Exception as exc:
                logger.exception("[Dados] erro event=%s", event_id)
                erros.append(f"{event_id}: {exc}")

        status = remote_call("status", temporada=args.ano)

        saida = {
            "ano": args.ano,
            "processados": processados,
            "jogadores_salvos": jogadores_salvos,
            "erros": erros,
            "status": status,
        }
        print(json.dumps(saida, ensure_ascii=False, indent=2, default=str))

        if erros:
            raise SystemExit(1)
    finally:
        fechar_cliente_sofascore()


if __name__ == "__main__":
    main()
