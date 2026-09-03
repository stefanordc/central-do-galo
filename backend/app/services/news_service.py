from __future__ import annotations

import hashlib
import json
from typing import Iterable
from uuid import UUID

from app.collectors.models import ArticleMetadata
from app.db.pool import pool


def obter_fonte_por_slug(slug: str) -> dict | None:
    sql = """
        select id, nome, slug, tipo, url_base, confiabilidade, oficial, ativo, configuracao
        from public.fontes
        where slug = %s
          and ativo = true
        limit 1
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (slug,))
            row = cur.fetchone()
            if not row:
                return None
            columns = [desc.name for desc in cur.description]
            return dict(zip(columns, row, strict=True))


def urls_ja_cadastradas(urls: Iterable[str]) -> set[str]:
    values = list(dict.fromkeys(urls))
    if not values:
        return set()

    sql = "select url from public.noticias where url = any(%s)"
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (values,))
            return {row[0] for row in cur.fetchall()}



def atualizar_imagem_noticia_por_url(
    url: str,
    imagem_url: str,
    *,
    sobrescrever: bool = False,
) -> bool:
    """Preenche a imagem e, opcionalmente, substitui uma imagem incorreta."""
    sql = """
        update public.noticias
        set imagem_url = %s,
            atualizado_em = now()
        where url = %s
          and (
                %s
                or imagem_url is null
                or btrim(imagem_url) = ''
          )
          and imagem_url is distinct from %s
        returning id
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (imagem_url, url, sobrescrever, imagem_url))
            updated = cur.fetchone() is not None
        conn.commit()
    return updated


def urls_sem_imagem(urls: Iterable[str]) -> set[str]:
    values = list(dict.fromkeys(urls))
    if not values:
        return set()

    sql = """
        select url
        from public.noticias
        where url = any(%s)
          and (imagem_url is null or btrim(imagem_url) = '')
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (values,))
            return {row[0] for row in cur.fetchall()}

def _hash_noticia(titulo: str, url: str) -> str:
    normalized = f"{titulo.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def salvar_noticia(
    fonte_id: UUID,
    oficial: bool,
    article: ArticleMetadata,
) -> UUID:
    sql = """
        insert into public.noticias (
            fonte_id,
            titulo,
            url,
            resumo,
            imagem_url,
            categoria,
            oficial,
            publicado_em,
            hash_conteudo,
            metadados,
            ativo
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, true)
        on conflict (url) do update
        set titulo = excluded.titulo,
            resumo = coalesce(excluded.resumo, public.noticias.resumo),
            imagem_url = coalesce(excluded.imagem_url, public.noticias.imagem_url),
            categoria = coalesce(excluded.categoria, public.noticias.categoria),
            publicado_em = coalesce(excluded.publicado_em, public.noticias.publicado_em),
            hash_conteudo = excluded.hash_conteudo,
            metadados = public.noticias.metadados || excluded.metadados,
            ativo = true,
            atualizado_em = now()
        returning id
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    fonte_id,
                    article.titulo,
                    article.url,
                    article.resumo,
                    article.imagem_url,
                    article.categoria,
                    oficial,
                    article.publicado_em,
                    _hash_noticia(article.titulo, article.url),
                    json.dumps(article.metadados, ensure_ascii=False),
                ),
            )
            noticia_id = cur.fetchone()[0]
        conn.commit()
    return noticia_id


def listar_noticias(
    limit: int = 50,
    offset: int = 0,
    categoria: str | None = None,
    fonte: str | None = None,
    busca: str | None = None,
) -> list[dict]:
    sql = """
        select
            n.id,
            n.titulo,
            n.url,
            n.resumo,
            n.imagem_url,
            n.categoria,
            n.oficial,
            n.publicado_em,
            n.coletado_em,
            f.id as fonte_id,
            f.nome as fonte_nome,
            f.slug as fonte_slug,
            f.confiabilidade as fonte_confiabilidade,
            coalesce(
                (
                    select jsonb_agg(
                        jsonb_build_object(
                            'nome', c.nome,
                            'slug', c.slug,
                            'principal', nc.principal
                        )
                        order by nc.principal desc, c.ordem, c.nome
                    )
                    from public.noticias_categorias nc
                    join public.categorias c on c.id = nc.categoria_id
                    where nc.noticia_id = n.id
                      and c.ativo = true
                ),
                '[]'::jsonb
            ) as categorias
        from public.noticias n
        join public.fontes f on f.id = n.fonte_id
        where n.ativo = true
          and f.ativo = true
          and n.url not in (
                'https://www.lance.com.br',
                'https://www.lance.com.br/'
          )
          and not (
                (f.slug = 'cnn-atletico' and (
                    lower(trim(n.titulo)) = lower('Atlético Mineiro | CNN Brasil')
                    or n.url = 'https://www.cnnbrasil.com.br/esportes/futebol/atletico-mineiro/'
                ))
                or
                (f.slug = 'falagalo' and (
                    lower(trim(n.titulo)) in (
                        'feed',
                        'wp json',
                        'quem somos - falagalo',
                        'falagalo - atlético mineiro - galo - notícias - tudo sobre o galo'
                    )
                    or n.url in (
                        'https://falagalo.com.br/feed/',
                        'https://falagalo.com.br/wp-json/',
                        'https://falagalo.com.br/quem-somos/',
                        'https://falagalo.com.br/https-falagalo-com-br/'
                    )
                ))
          )
          and (%s::text is null or f.slug = %s)
          and (
                %s::text is null
                or n.titulo ilike '%%' || %s || '%%'
                or coalesce(n.resumo, '') ilike '%%' || %s || '%%'
          )
          and (
                %s::text is null
                or exists (
                    select 1
                    from public.noticias_categorias nc_filter
                    join public.categorias c_filter on c_filter.id = nc_filter.categoria_id
                    where nc_filter.noticia_id = n.id
                      and c_filter.slug = %s
                      and c_filter.ativo = true
                )
          )
        order by coalesce(n.publicado_em, n.coletado_em) desc
        limit %s offset %s
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (fonte, fonte, busca, busca, busca, categoria, categoria, limit, offset),
            )
            columns = [desc.name for desc in cur.description]
            return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]
