from app.db.pool import pool


def obter_capa_site() -> dict:
    sql = """
        select
            id,
            ativo,
            tipo,
            media_url,
            atualizado_em
        from public.configuracao_capa_site
        where id = 1
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()

            if row is None:
                return {
                    "id": 1,
                    "ativo": False,
                    "tipo": "imagem",
                    "media_url": None,
                    "atualizado_em": None,
                }

            colunas = [desc.name for desc in cur.description]
            return dict(zip(colunas, row, strict=True))


def atualizar_capa_site(
    *,
    ativo: bool,
    tipo: str,
    media_url: str | None,
) -> dict:
    tipo_limpo = tipo.strip().lower()
    if tipo_limpo not in {"imagem", "video"}:
        raise ValueError("Tipo de mídia inválido.")

    url_limpa = (media_url or "").strip() or None

    if ativo and not url_limpa:
        raise ValueError("Informe a URL da imagem ou do vídeo antes de ativar a capa.")

    sql = """
        insert into public.configuracao_capa_site (
            id,
            ativo,
            tipo,
            media_url,
            atualizado_em
        )
        values (
            1,
            %(ativo)s,
            %(tipo)s,
            %(media_url)s,
            now()
        )
        on conflict (id) do update
        set ativo = excluded.ativo,
            tipo = excluded.tipo,
            media_url = excluded.media_url,
            atualizado_em = now()
        returning
            id,
            ativo,
            tipo,
            media_url,
            atualizado_em
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "ativo": ativo,
                    "tipo": tipo_limpo,
                    "media_url": url_limpa,
                },
            )
            colunas = [desc.name for desc in cur.description]
            row = cur.fetchone()

        conn.commit()

    return dict(zip(colunas, row, strict=True))
