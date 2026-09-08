from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.pool import pool
from app.services.jogo_service import (
    fechar_cliente_sofascore,
    sincronizacao_inicial,
    sincronizar_agenda,
    sincronizar_autores_gols,
    sincronizar_historico_maximo,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("central_galo.jogos.cli")


def _contar_pendentes_gols() -> int:
    sql = """
        select count(*)
        from public.jogos
        where status = 'finalizado'
          and left(id_externo, 10) = 'sofascore:'
          and not (coalesce(metadados, '{}'::jsonb) ? 'gols')
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()

    return int(row[0] or 0) if row else 0


def _sincronizar_todos_gols(
    *,
    tamanho_lote: int = 80,
    pausa_entre_lotes: float = 1.0,
    max_sem_progresso: int = 3,
) -> dict:
    tamanho_lote = max(1, min(int(tamanho_lote), 80))
    max_sem_progresso = max(1, int(max_sem_progresso))

    pendentes_iniciais = _contar_pendentes_gols()
    pendentes_antes = pendentes_iniciais

    logger.info(
        "[Jogos] iniciando preenchimento completo de autores dos gols | "
        "pendentes=%s | lote=%s",
        pendentes_iniciais,
        tamanho_lote,
    )

    lotes = 0
    erros_total = 0
    sem_progresso = 0
    interrompido_por_falhas = False

    while True:
        pendentes_antes = _contar_pendentes_gols()

        if pendentes_antes <= 0:
            break

        lotes += 1

        logger.info(
            "[Jogos] lote %s | pendentes antes=%s",
            lotes,
            pendentes_antes,
        )

        resultado = sincronizar_autores_gols(tamanho_lote)

        erros_lote = resultado.get("erros") or []
        erros_total += len(erros_lote)

        pendentes_depois = _contar_pendentes_gols()
        processados_reais = max(0, pendentes_antes - pendentes_depois)

        logger.info(
            "[Jogos] lote %s concluído | processados=%s | "
            "erros=%s | pendentes depois=%s",
            lotes,
            processados_reais,
            len(erros_lote),
            pendentes_depois,
        )

        if pendentes_depois <= 0:
            break

        if pendentes_depois >= pendentes_antes:
            sem_progresso += 1
            logger.warning(
                "[Jogos] lote sem progresso (%s/%s). "
                "Alguns jogos podem não possuir incidents disponíveis.",
                sem_progresso,
                max_sem_progresso,
            )
        else:
            sem_progresso = 0

        if sem_progresso >= max_sem_progresso:
            interrompido_por_falhas = True
            logger.warning(
                "[Jogos] interrompendo após %s lotes consecutivos sem progresso. "
                "Os jogos restantes poderão ser tentados novamente depois.",
                max_sem_progresso,
            )
            break

        if pausa_entre_lotes > 0:
            time.sleep(pausa_entre_lotes)

    pendentes_finais = _contar_pendentes_gols()

    return {
        "fonte": "sofascore",
        "modo": "gols-todos",
        "pendentes_iniciais": pendentes_iniciais,
        "processados_nesta_execucao": max(
            0,
            pendentes_iniciais - pendentes_finais,
        ),
        "pendentes_finais": pendentes_finais,
        "lotes_executados": lotes,
        "erros_observados": erros_total,
        "interrompido_por_falhas": interrompido_por_falhas,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza os jogos do Atlético-MG com o Sofascore."
    )
    parser.add_argument(
        "--modo",
        choices=[
            "inicial",
            "atual",
            "historico",
            "gols",
            "gols-todos",
        ],
        default="atual",
        help=(
            "inicial = histórico + agenda + gols recentes; "
            "atual = últimos e próximos jogos; "
            "historico = tenta voltar até 2000; "
            "gols = preenche um lote de autores dos gols; "
            "gols-todos = percorre todos os jogos finalizados pendentes."
        ),
    )
    parser.add_argument(
        "--limite-gols",
        type=int,
        default=12,
        help=(
            "Quantidade máxima de jogos no modo 'gols'. "
            "O serviço aceita no máximo 80 por lote."
        ),
    )
    parser.add_argument(
        "--tamanho-lote",
        type=int,
        default=80,
        help=(
            "Tamanho de cada lote no modo 'gols-todos'. "
            "Máximo: 80."
        ),
    )
    parser.add_argument(
        "--pausa-lotes",
        type=float,
        default=1.0,
        help="Pausa em segundos entre os lotes do modo 'gols-todos'.",
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

        elif args.modo == "gols-todos":
            resultado = _sincronizar_todos_gols(
                tamanho_lote=args.tamanho_lote,
                pausa_entre_lotes=args.pausa_lotes,
            )

        else:
            resultado = sincronizar_agenda()

        print(
            json.dumps(
                resultado,
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )

    finally:
        fechar_cliente_sofascore()
        pool.close()


if __name__ == "__main__":
    main()
