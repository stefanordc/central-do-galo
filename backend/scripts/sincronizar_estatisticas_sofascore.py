from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.pool import pool
from app.services.dados_service import sincronizar_estatisticas_sofascore
from app.services.jogo_service import fechar_cliente_sofascore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("central_galo.dados.cli")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Coleta estatísticas coletivas e individuais do SofaScore."
    )
    parser.add_argument(
        "--ano",
        type=int,
        default=None,
        help="Processa somente um ano. Ex.: --ano 2026.",
    )
    parser.add_argument(
        "--desde",
        type=int,
        default=None,
        help="Primeiro ano do intervalo. Ex.: --desde 2020.",
    )
    parser.add_argument(
        "--ate",
        type=int,
        default=None,
        help="Último ano do intervalo. O padrão é o ano atual.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Limita a quantidade de jogos processados em cada ano.",
    )
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Refaz jogos que já possuem estatísticas armazenadas.",
    )
    args = parser.parse_args()

    if args.ano is not None:
        anos = [args.ano]
    elif args.desde is not None:
        ate = args.ate or datetime.now().year
        if ate < args.desde:
            raise SystemExit("--ate não pode ser menor que --desde.")
        anos = list(range(args.desde, ate + 1))
    else:
        anos = [datetime.now().year]

    pool.open()
    resultados = []
    try:
        for indice, ano in enumerate(anos, 1):
            logger.info("[Dados] ano %s/%s: %s", indice, len(anos), ano)
            resultado = sincronizar_estatisticas_sofascore(
                ano,
                forcar=args.forcar,
                limite=args.limite,
            )
            resultados.append(resultado)

        saida = {
            "fonte": "sofascore",
            "anos": anos,
            "processados": sum(item.get("processados", 0) for item in resultados),
            "jogadores_salvos": sum(item.get("jogadores_salvos", 0) for item in resultados),
            "erros": sum(len(item.get("erros", [])) for item in resultados),
            "detalhes": resultados,
        }
        print(json.dumps(saida, ensure_ascii=False, indent=2, default=str))
    finally:
        fechar_cliente_sofascore()
        pool.close()


if __name__ == "__main__":
    main()
