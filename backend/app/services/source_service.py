import json
import re

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


def listar_canais_youtube_admin() -> list[dict]:
    sql = """
        select
            id,
            nome,
            slug,
            url_base,
            confiabilidade,
            oficial,
            ativo,
            configuracao
        from public.fontes
        where tipo = 'youtube'
        order by oficial desc, nome asc
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            colunas = [desc.name for desc in cur.description]
            return [dict(zip(colunas, row, strict=True)) for row in cur.fetchall()]


def _extrair_handle_youtube(valor: str) -> str:
    entrada = valor.strip()
    if not entrada:
        raise ValueError("Informe a URL ou o @handle do canal.")

    if entrada.startswith("@"):
        handle = entrada
    else:
        match = re.search(
            r"(?:https?://)?(?:www\.)?youtube\.com/(@[A-Za-z0-9._-]+)",
            entrada,
            flags=re.IGNORECASE,
        )
        if not match:
            raise ValueError("Informe uma URL válida do YouTube no formato https://www.youtube.com/@canal/videos.")
        handle = match.group(1)

    if len(handle) < 2:
        raise ValueError("Handle do YouTube inválido.")

    return handle


def _slug_youtube(handle: str) -> str:
    identificador = handle.lstrip("@").lower()
    identificador = re.sub(r"[^a-z0-9]+", "-", identificador).strip("-")
    if not identificador:
        raise ValueError("Não foi possível gerar o identificador do canal.")
    return f"youtube-{identificador}"


def criar_canal_youtube(
    *,
    nome: str,
    url: str,
    oficial: bool = False,
    confiabilidade: int = 80,
) -> dict:
    nome_limpo = nome.strip()
    if not nome_limpo:
        raise ValueError("Informe o nome do canal.")

    handle = _extrair_handle_youtube(url)
    slug = _slug_youtube(handle)
    url_base = f"https://www.youtube.com/{handle}"

    configuracao = {
        "handle": handle,
        "plataforma": "youtube",
        "videos_url": f"{url_base}/videos",
        "shorts_url": f"{url_base}/shorts",
        "streams_url": f"{url_base}/streams",
    }

    sql = """
        insert into public.fontes (
            nome,
            slug,
            tipo,
            url_base,
            confiabilidade,
            oficial,
            ativo,
            configuracao
        )
        values (
            %(nome)s,
            %(slug)s,
            'youtube',
            %(url_base)s,
            %(confiabilidade)s,
            %(oficial)s,
            true,
            %(configuracao)s::jsonb
        )
        returning
            id,
            nome,
            slug,
            tipo,
            url_base,
            confiabilidade,
            oficial,
            ativo,
            configuracao
    """

    parametros = {
        "nome": nome_limpo,
        "slug": slug,
        "url_base": url_base,
        "confiabilidade": confiabilidade,
        "oficial": oficial,
        "configuracao": json.dumps(configuracao, ensure_ascii=False),
    }

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            colunas = [desc.name for desc in cur.description]
            row = cur.fetchone()
            return dict(zip(colunas, row, strict=True))
