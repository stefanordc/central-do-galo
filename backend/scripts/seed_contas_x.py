from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.pool import close_pool, open_pool, pool

CONTAS = [
    ("Atlético", "Atletico", True, 100),
    ("@pedfaria", "pedfaria", False, 80),
    ("@ohenriqueandre", "ohenriqueandre", False, 80),
    ("@Igortep", "Igortep", False, 80),
    ("@GaloCareca21", "GaloCareca21", False, 80),
    ("@InfoGalo_", "InfoGalo_", False, 80),
]


def main() -> int:
    open_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                for nome, usuario, oficial, confiabilidade in CONTAS:
                    cur.execute(
                        """
                        insert into public.contas_x (nome, usuario, oficial, confiabilidade, ativo)
                        values (%s, %s, %s, %s, true)
                        on conflict (usuario) do update
                        set nome = excluded.nome,
                            oficial = excluded.oficial,
                            confiabilidade = excluded.confiabilidade,
                            ativo = true
                        """,
                        (nome, usuario, oficial, confiabilidade),
                    )
                conn.commit()

            with conn.cursor() as cur:
                cur.execute(
                    """
                    select usuario, ativo, oficial, x_user_id, status_sync, sync_erro
                    from public.contas_x
                    where lower(usuario) = any(%s)
                    order by case when lower(usuario) = 'atletico' then 0 else 1 end, lower(usuario)
                    """,
                    ([item[1].lower() for item in CONTAS],),
                )
                rows = cur.fetchall()

        print("=== CONTAS DO RADAR DO X ===")
        for usuario, ativo, oficial, x_user_id, status_sync, sync_erro in rows:
            print(
                f"@{usuario}: ativo={ativo} | oficial={oficial} | "
                f"x_user_id={x_user_id or '-'} | status={status_sync}"
                + (f" | erro={sync_erro}" if sync_erro else "")
            )
        return 0
    finally:
        close_pool()


if __name__ == "__main__":
    raise SystemExit(main())
