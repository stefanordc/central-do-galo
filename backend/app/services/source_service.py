from app.db.pool import pool


def listar_fontes() -> list[dict]:
    sql = """
        select
            id,
            nome,
            slug,
            tipo,
            url_base,
            url_feed,
            confiabilidade,
            oficial,
            ativo
        from public.fontes
        where ativo = true
        order by oficial desc, confiabilidade desc, nome asc
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            colunas = [desc.name for desc in cur.description]
            return [dict(zip(colunas, row, strict=True)) for row in cur.fetchall()]
