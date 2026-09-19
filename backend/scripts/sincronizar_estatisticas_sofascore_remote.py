from __future__ import annotations

import argparse
import json
import logging
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
from app.services.jogo_service import _cliente_sofascore, _sofascore_get, fechar_cliente_sofascore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("central_galo.dados.remote")

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
                lineups = _sofascore_get(f"/event/{event_id}/lineups")

                logger.info(
                    "[Dados] lineups diretas home_players=%s away_players=%s",
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
