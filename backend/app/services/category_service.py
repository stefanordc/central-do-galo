from __future__ import annotations

from app.db.pool import pool


def listar_categorias() -> list[dict]:
    sql = """
        select
            c.id,
            c.nome,
            c.slug,
            c.descricao,
            c.ordem,
            count(distinct n.id)::int as total_noticias
        from public.categorias c
        left join public.noticias_categorias nc on nc.categoria_id = c.id
        left join public.noticias n on n.id = nc.noticia_id and n.ativo = true
        where c.ativo = true
        group by c.id, c.nome, c.slug, c.descricao, c.ordem
        having count(distinct n.id) > 0 or c.slug = 'geral'
        order by c.ordem, c.nome
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            colunas = [desc.name for desc in cur.description]
            return [dict(zip(colunas, row, strict=True)) for row in cur.fetchall()]
