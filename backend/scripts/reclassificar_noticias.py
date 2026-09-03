from __future__ import annotations

from app.db.pool import close_pool, open_pool, pool
from app.services.news_classifier import save_news_categories


def main() -> None:
    open_pool()
    try:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select id, titulo, resumo
                    from public.noticias
                    where ativo = true
                    order by coalesce(publicado_em, coletado_em) desc
                    """
                )
                noticias = cur.fetchall()

        total = len(noticias)
        for indice, (noticia_id, titulo, resumo) in enumerate(noticias, start=1):
            save_news_categories(noticia_id, titulo, resumo)
            print(f"{indice}/{total} | {titulo}")

        print(f"\n{total} notícias classificadas.")
    finally:
        close_pool()


if __name__ == "__main__":
    main()
