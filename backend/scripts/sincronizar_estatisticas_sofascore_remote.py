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
from app.services.jogo_service import _cliente_sofascore, _sofascore_get, fechar_cliente_sofascore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("central_galo.dados.remote")

def _fetch_widget_lineups(event_id: int, tentativas: int = 3) -> dict:
    url = f"https://widgets.sofascore.com/embed/lineups?id={event_id}"
    cliente = _cliente_sofascore()
    ultimo_erro: Exception | None = None

    for tentativa in range(1, tentativas + 1):
        try:
            logger.info(
                "[Dados] abrindo widget no Chrome event=%s tentativa=%s/%s",
                event_id,
                tentativa,
                tentativas,
            )
            cliente.driver.get(url)
            time.sleep(1.5)

            # O widget é uma página Next.js. O payload das escalações fica no
            # script __NEXT_DATA__, mesmo quando a UI ainda está renderizando.
            script_text = cliente.driver.execute_script(
                """
                const el = document.getElementById('__NEXT_DATA__');
                return el ? el.textContent : '';
                """
            )

            if not script_text:
                page_source = cliente.driver.page_source or ""
                match = re.search(
                    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                    page_source,
                    re.DOTALL,
                )
                script_text = match.group(1) if match else ""

            if not script_text:
                body_text = cliente.driver.execute_script(
                    "return document.body ? document.body.innerText : '';"
                )
                raise RuntimeError(
                    "Widget sem __NEXT_DATA__. "
                    f"Body inicial={str(body_text)[:180]!r}"
                )

            data = json.loads(script_text)
            page_props = data.get("props", {}).get("pageProps", {})
            lineups = page_props.get("initialLineups") or {}

            if isinstance(lineups, dict) and (
                isinstance(lineups.get("home"), dict)
                or isinstance(lineups.get("away"), dict)
            ):
                # Volta à origem principal para preservar o fluxo usado pelo
                # cliente híbrido na próxima chamada ao SofaScore.
                cliente.driver.get("https://www.sofascore.com/")
                time.sleep(0.4)
                cliente.renovar_sessao()
                return lineups

            raise RuntimeError(
                f"Widget sem initialLineups. pageProps={list(page_props.keys())}"
            )
        except Exception as exc:
            ultimo_erro = exc
            logger.warning(
                "[Dados] widget via Chrome falhou event=%s tentativa=%s: %s",
                event_id,
                tentativa,
                str(exc).splitlines()[0],
            )
            try:
                cliente.driver.get("https://www.sofascore.com/")
                time.sleep(0.8)
                cliente.renovar_sessao()
            except Exception:
                pass

            if tentativa < tentativas:
                time.sleep(1.2 * tentativa + random.uniform(0.2, 0.8))

    raise RuntimeError(
        f"Falha no widget de lineups do evento {event_id}: {ultimo_erro}"
    )


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
