from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.pool import pool
from app.services.jogo_service import (
    sincronizacao_inicial,
    sincronizar_agenda,
    sincronizar_autores_gols,
    sincronizar_historico_maximo,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza os jogos do Atlético-MG com a API-Football."
    )
    parser.add_argument(
        "--modo",
        choices=["inicial", "atual", "historico", "gols"],
        default="atual",
        help=(
            "inicial = máximo histórico + agenda + gols recentes; "
            "atual = últimos/próximos jogos; "
            "historico = máximo período permitido pela API; "
            "gols = preenche autores dos gols."
        ),
    )
    parser.add_argument(
        "--limite-gols",
        type=int,
        default=12,
        help="Quantidade máxima de partidas finalizadas para buscar autores dos gols.",
    )
    args = parser.parse_args()

    pool.open()

    try:
        if args.modo == "inicial":
            resultado = sincronizacao_inicial()
        elif args.modo == "historico":
            resultado = sincronizar_historico_maximo()
        elif args.modo == "gols":
            resultado = sincronizar_autores_gols(args.limite_gols)
        else:
            resultado = sincronizar_agenda()

        print(json.dumps(resultado, ensure_ascii=False, indent=2, default=str))
    finally:
        pool.close()


if __name__ == "__main__":
    main()
