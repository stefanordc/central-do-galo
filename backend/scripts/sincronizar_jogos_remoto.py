from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jogo_service import (
    SOFASCORE_TEAM_ID,
    _buscar_pagina_time,
    fechar_cliente_sofascore,
)
from app.services.jogos_collector_store import remote_call

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("central_galo.jogos_remoto")


def _coletar_eventos() -> tuple[list[dict], int]:
    eventos: list[dict] = []

    logger.info("[Jogos] buscando ultima pagina de jogos passados")
    passados = _buscar_pagina_time("last", 0)
    pagina_passados = passados.get("events") or []
    if isinstance(pagina_passados, list):
        eventos.extend(pagina_passados)

    if not pagina_passados:
        logger.warning(
            "[Jogos] resposta LAST sem events | chaves=%s | payload=%s",
            list(passados.keys()),
            json.dumps(passados, ensure_ascii=False, default=str)[:1800],
        )

    pagina = 0
    paginas_futuras = 0

    while pagina < 10:
        logger.info("[Jogos] buscando pagina futura %s", pagina)
        dados = _buscar_pagina_time("next", pagina)
        pagina_eventos = dados.get("events") or []

        if isinstance(pagina_eventos, list):
            eventos.extend(pagina_eventos)

        if not pagina_eventos:
            logger.warning(
                "[Jogos] resposta NEXT pagina=%s sem events | chaves=%s | payload=%s",
                pagina,
                list(dados.keys()),
                json.dumps(dados, ensure_ascii=False, default=str)[:1800],
            )

        paginas_futuras += 1

        if not dados.get("hasNextPage"):
            break

        pagina += 1

    unicos: dict[int, dict] = {}
    for evento in eventos:
        event_id = evento.get("id")
        if isinstance(event_id, int):
            unicos[event_id] = evento

    ordenados = sorted(
        unicos.values(),
        key=lambda item: item.get("startTimestamp") or 0,
    )
    return ordenados, paginas_futuras


def _enviar_lote(lote: list[dict], tentativa_maxima: int = 3) -> dict:
    ultimo_erro: Exception | None = None

    for tentativa in range(1, tentativa_maxima + 1):
        try:
            return remote_call("save_events", eventos=lote)
        except Exception as exc:
            ultimo_erro = exc
            logger.warning(
                "[Jogos] falha ao enviar lote tentativa=%s/%s: %s",
                tentativa,
                tentativa_maxima,
                exc,
            )
            if tentativa < tentativa_maxima:
                time.sleep(tentativa * 3)

    raise RuntimeError(f"Falha definitiva ao enviar lote: {ultimo_erro}")


def main() -> int:
    print("\n=== CENTRAL DO GALO | SINCRONIZACAO REMOTA DE JOGOS ===")
    print(f"SofaScore team_id: {SOFASCORE_TEAM_ID}")

    try:
        eventos, paginas_futuras = _coletar_eventos()
        print(f"Eventos unicos encontrados: {len(eventos)}")

        total_salvos = 0
        erros: list[str] = []
        tamanho_lote = 20

        for inicio in range(0, len(eventos), tamanho_lote):
            lote = eventos[inicio : inicio + tamanho_lote]
            logger.info(
                "[Jogos] enviando lote %s-%s de %s",
                inicio + 1,
                inicio + len(lote),
                len(eventos),
            )

            resultado = _enviar_lote(lote)
            total_salvos += int(resultado.get("salvos") or 0)
            erros.extend(str(item) for item in (resultado.get("erros") or []))

        resumo = {
            "fonte": "sofascore",
            "team_id": SOFASCORE_TEAM_ID,
            "encontrados": len(eventos),
            "salvos": total_salvos,
            "paginas_futuras": paginas_futuras,
            "erros": erros,
        }

        print(json.dumps(resumo, ensure_ascii=False, indent=2))

        if erros:
            logger.warning("[Jogos] sincronizacao terminou com %s erro(s)", len(erros))
            return 1

        return 0
    except Exception as exc:
        logger.exception("[Jogos] falha geral: %s", exc)
        return 1
    finally:
        fechar_cliente_sofascore()


if __name__ == "__main__":
    raise SystemExit(main())
