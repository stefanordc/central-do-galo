from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.collectors.runner import NewsCollectorRunner  # noqa: E402
from app.db.pool import close_pool, open_pool  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Coletor de notícias do Central do Galo")
    parser.add_argument("--fonte", help="Slug de uma fonte específica")
    parser.add_argument("--delay", type=float, default=0.6)
    parser.add_argument(
        "--historico",
        action="store_true",
        help="Percorre até 25 páginas por fonte para preencher o histórico disponível.",
    )
    parser.add_argument(
        "--max-paginas",
        type=int,
        default=25,
        help="Número máximo de páginas por fonte no modo histórico. Padrão: 25.",
    )
    parser.add_argument(
        "--sitemaps",
        action="store_true",
        help="Também percorre sitemaps. Pode descobrir um volume muito maior de URLs.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Retorna código de erro se alguma fonte tiver erro ou, no modo recente, "
            "não encontrar nenhum candidato."
        ),
    )
    args = parser.parse_args()

    usar_store_remoto = bool((os.getenv("NEWS_REMOTE_STORE_URL") or "").strip())

    if not usar_store_remoto:
        open_pool()

    try:
        runner = NewsCollectorRunner(
            delay_seconds=args.delay,
            max_history_pages=args.max_paginas,
        )
        results = (
            [
                runner.collect_source(
                    args.fonte,
                    historical=args.historico,
                    include_sitemaps=args.sitemaps,
                )
            ]
            if args.fonte
            else runner.collect_all(
                historical=args.historico,
                include_sitemaps=args.sitemaps,
            )
        )

        modo = "HISTÓRICO" if args.historico else "RECENTE"
        print(f"\n=== CENTRAL DO GALO | COLETA DE NOTÍCIAS | {modo} ===")
        problemas = []

        for result in results:
            resumo = (
                f"{result.fonte}: "
                f"candidatos={result.candidatos} | "
                f"novos={result.novos_encontrados} | "
                f"inseridos={result.inseridos} | "
                f"enriquecidos={result.enriquecidos} | "
                f"paginas={result.paginas_lidas} | "
                f"sitemaps={result.sitemaps_lidos} | "
                f"robots={result.ignorados_robots} | "
                f"erros={result.erros} | "
                f"status={result.mensagem}"
            )
            print(resumo)

            sem_candidatos = not args.historico and result.candidatos == 0
            if result.erros > 0 or sem_candidatos:
                motivos = []
                if result.erros > 0:
                    motivos.append(f"{result.erros} erro(s)")
                if sem_candidatos:
                    motivos.append("0 candidatos")
                detalhe = f"{result.fonte}: {', '.join(motivos)} | {result.mensagem}"
                problemas.append(detalhe)

                if os.getenv("GITHUB_ACTIONS") == "true":
                    print(
                        f"::error title=Falha na coleta de {result.fonte}::{detalhe}"
                    )

        if args.strict and problemas:
            print(
                "\nColeta marcada como falha porque uma ou mais fontes precisam de revisão:",
                file=sys.stderr,
            )
            for problema in problemas:
                print(f"- {problema}", file=sys.stderr)
            raise SystemExit(2)
    finally:
        if not usar_store_remoto:
            close_pool()


if __name__ == "__main__":
    main()
