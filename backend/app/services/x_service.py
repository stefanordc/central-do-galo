from collections import OrderedDict

from app.db.pool import pool


def listar_contas_x() -> list[dict]:
    sql = """
        select
            c.id,
            c.nome,
            c.usuario,
            c.foto_url,
            c.oficial,
            c.confiabilidade,
            c.ativo,
            c.ultima_sincronizacao,
            c.status_sync,
            c.sync_erro
        from public.contas_x c
        where c.ativo = true
        order by
            case when lower(c.usuario) = 'atletico' then 0 else 1 end,
            coalesce(
                (
                    select max(coalesce(p.publicado_em, p.coletado_em))
                    from public.posts_x p
                    where p.conta_id = c.id
                      and p.ativo = true
                ),
                c.criado_em
            ) desc,
            md5(lower(c.usuario))
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            colunas = [desc.name for desc in cur.description]
            return [dict(zip(colunas, row, strict=True)) for row in cur.fetchall()]


def listar_posts_x_agrupados(limit_por_conta: int = 3) -> list[dict]:
    sql = """
        with posts_ranqueados as (
            select
                p.id,
                p.conta_id,
                p.post_id,
                p.url,
                p.texto,
                p.publicado_em,
                p.coletado_em,
                p.metricas,
                p.midia,
                p.embed_html,
                p.embed_status,
                p.embed_atualizado_em,
                coalesce(p.publicado_em, p.coletado_em) as ordenacao_post,
                row_number() over (
                    partition by p.conta_id
                    order by coalesce(p.publicado_em, p.coletado_em) desc, p.post_id desc
                ) as rn
            from public.posts_x p
            where p.ativo = true
        ),
        conta_ultima_publicacao as (
            select
                conta_id,
                max(ordenacao_post) as ultima_publicacao
            from posts_ranqueados
            group by conta_id
        )
        select
            c.id as conta_id,
            c.nome as conta_nome,
            c.usuario as conta_usuario,
            c.foto_url as conta_foto_url,
            c.oficial as conta_oficial,
            c.confiabilidade as conta_confiabilidade,
            c.ultima_sincronizacao,
            c.status_sync,
            c.sync_erro,
            p.id as post_pk,
            p.post_id,
            p.url,
            p.texto,
            p.publicado_em,
            p.coletado_em,
            p.metricas,
            p.midia,
            p.embed_html,
            p.embed_status,
            p.embed_atualizado_em
        from public.contas_x c
        left join posts_ranqueados p
            on p.conta_id = c.id
           and p.rn <= %s
        left join conta_ultima_publicacao cup
            on cup.conta_id = c.id
        where c.ativo = true
        order by
            case when lower(c.usuario) = 'atletico' then 0 else 1 end,
            cup.ultima_publicacao desc nulls last,
            md5(lower(c.usuario)),
            p.ordenacao_post desc nulls last
    """

    contas: OrderedDict[str, dict] = OrderedDict()

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limit_por_conta,))
            colunas = [desc.name for desc in cur.description]

            for row in cur.fetchall():
                registro = dict(zip(colunas, row, strict=True))
                conta_id = str(registro["conta_id"])

                if conta_id not in contas:
                    contas[conta_id] = {
                        "id": registro["conta_id"],
                        "nome": registro["conta_nome"],
                        "usuario": registro["conta_usuario"],
                        "foto_url": registro["conta_foto_url"],
                        "oficial": registro["conta_oficial"],
                        "confiabilidade": registro["conta_confiabilidade"],
                        "ultima_sincronizacao": registro["ultima_sincronizacao"],
                        "status_sync": registro["status_sync"],
                        "sync_erro": registro["sync_erro"],
                        "posts": [],
                    }

                if registro["post_pk"] is not None:
                    contas[conta_id]["posts"].append(
                        {
                            "id": registro["post_pk"],
                            "post_id": registro["post_id"],
                            "url": registro["url"],
                            "texto": registro["texto"],
                            "publicado_em": registro["publicado_em"],
                            "coletado_em": registro["coletado_em"],
                            "metricas": registro["metricas"] or {},
                            "midia": registro["midia"] or [],
                            "embed_html": registro["embed_html"],
                            "embed_status": registro["embed_status"],
                            "embed_atualizado_em": registro["embed_atualizado_em"],
                        }
                    )

    return list(contas.values())


def listar_feed_x(limit: int = 60, offset: int = 0, usuario: str | None = None) -> list[dict]:
    usuario_normalizado = (usuario or "").strip()

    sql = """
        select
            p.id,
            p.post_id,
            p.url,
            p.texto,
            p.publicado_em,
            p.coletado_em,
            p.metricas,
            p.midia,
            p.embed_html,
            p.embed_status,
            p.embed_atualizado_em,
            c.id as conta_id,
            c.nome as conta_nome,
            c.usuario as conta_usuario,
            c.foto_url as conta_foto_url,
            c.oficial as conta_oficial
        from public.posts_x p
        join public.contas_x c on c.id = p.conta_id
        where p.ativo = true
          and c.ativo = true
    """

    parametros: list[object] = []

    if usuario_normalizado:
        sql += " and lower(c.usuario) = lower(%s)"
        parametros.append(usuario_normalizado)

    sql += """
        order by coalesce(p.publicado_em, p.coletado_em) desc, p.post_id desc
        limit %s offset %s
    """
    parametros.extend([limit, offset])

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(parametros))
            colunas = [desc.name for desc in cur.description]
            return [dict(zip(colunas, row, strict=True)) for row in cur.fetchall()]


def obter_status_x() -> dict:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select
                    count(*) filter (where ativo = true) as contas_ativas,
                    count(*) filter (where ativo = true and status_sync = 'ok') as contas_ok,
                    count(*) filter (where ativo = true and status_sync = 'erro') as contas_erro,
                    count(*) filter (where ativo = true and ultima_sincronizacao is null) as nunca_sincronizadas
                from public.contas_x
                """
            )
            contas = cur.fetchone()

            cur.execute(
                """
                select
                    count(*) as posts_total,
                    count(*) filter (where ativo = true) as posts_ativos,
                    count(*) filter (where ativo = true and embed_html is not null and embed_status = 'ok') as embeds_ok,
                    count(*) filter (where ativo = true and (embed_html is null or embed_status <> 'ok')) as embeds_erro
                from public.posts_x
                """
            )
            posts = cur.fetchone()

    return {
        "contas_ativas": contas[0],
        "contas_ok": contas[1],
        "contas_erro": contas[2],
        "nunca_sincronizadas": contas[3],
        "posts_total": posts[0],
        "posts_ativos": posts[1],
        "embeds_ok": posts[2],
        "embeds_erro": posts[3],
    }
