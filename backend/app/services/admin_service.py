import re
from urllib.parse import urlparse

from app.db.pool import pool


_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_X_USER_RE = re.compile(r"^[A-Za-z0-9_]{1,15}$")


def normalizar_slug(slug: str) -> str:
    valor = (slug or "").strip().lower()
    valor = re.sub(r"[^a-z0-9]+", "-", valor).strip("-")
    if not valor or not _SLUG_RE.fullmatch(valor):
        raise ValueError("Slug inválido.")
    return valor


def normalizar_usuario_x(valor: str) -> str:
    usuario = (valor or "").strip()
    if not usuario:
        raise ValueError("Informe o usuário ou a URL do perfil do X.")

    if usuario.startswith("http://") or usuario.startswith("https://"):
        parsed = urlparse(usuario)
        host = parsed.netloc.lower().removeprefix("www.")
        if host not in {"x.com", "twitter.com"}:
            raise ValueError("A URL precisa ser de x.com ou twitter.com.")
        partes = [parte for parte in parsed.path.split("/") if parte]
        if not partes:
            raise ValueError("Não foi possível identificar o usuário na URL.")
        usuario = partes[0]

    usuario = usuario.split("?")[0].lstrip("@").strip()
    if not _X_USER_RE.fullmatch(usuario):
        raise ValueError("Usuário do X inválido.")
    return usuario


def listar_paginas_admin() -> list[dict]:
    sql = """
        select id, titulo, slug, conteudo, ativo, criado_em, atualizado_em
        from public.paginas
        order by criado_em desc
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            colunas = [desc.name for desc in cur.description]
            return [dict(zip(colunas, row, strict=True)) for row in cur.fetchall()]


def criar_pagina(*, titulo: str, slug: str, conteudo: str, ativo: bool = True) -> dict:
    titulo_limpo = (titulo or "").strip()
    conteudo_limpo = (conteudo or "").strip()
    slug_limpo = normalizar_slug(slug)

    if len(titulo_limpo) < 2:
        raise ValueError("Informe um título válido.")
    if not conteudo_limpo:
        raise ValueError("Informe o conteúdo da página.")

    sql = """
        insert into public.paginas (titulo, slug, conteudo, ativo)
        values (%s, %s, %s, %s)
        returning id, titulo, slug, conteudo, ativo, criado_em, atualizado_em
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (titulo_limpo, slug_limpo, conteudo_limpo, ativo))
            row = cur.fetchone()
            colunas = [desc.name for desc in cur.description]
        conn.commit()
    return dict(zip(colunas, row, strict=True))


def obter_pagina_publica(slug: str) -> dict | None:
    slug_limpo = normalizar_slug(slug)
    sql = """
        select id, titulo, slug, conteudo, criado_em, atualizado_em
        from public.paginas
        where slug = %s and ativo = true
        limit 1
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (slug_limpo,))
            row = cur.fetchone()
            if row is None:
                return None
            colunas = [desc.name for desc in cur.description]
            return dict(zip(colunas, row, strict=True))


def listar_contas_x_admin() -> list[dict]:
    sql = """
        select id, nome, usuario, oficial, confiabilidade, ativo,
               ultima_sincronizacao, status_sync, sync_erro, criado_em
        from public.contas_x
        order by ativo desc, lower(usuario)
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            colunas = [desc.name for desc in cur.description]
            return [dict(zip(colunas, row, strict=True)) for row in cur.fetchall()]


def criar_conta_x(
    *,
    nome: str,
    usuario: str,
    oficial: bool = False,
    confiabilidade: int = 80,
) -> dict:
    usuario_limpo = normalizar_usuario_x(usuario)
    nome_limpo = (nome or "").strip() or f"@{usuario_limpo}"
    confiabilidade = max(0, min(100, int(confiabilidade)))

    sql = """
        insert into public.contas_x (
            nome, usuario, oficial, confiabilidade, ativo, status_sync, sync_erro
        )
        values (%s, %s, %s, %s, true, 'pendente', null)
        returning id, nome, usuario, oficial, confiabilidade, ativo,
                  ultima_sincronizacao, status_sync, sync_erro, criado_em
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (nome_limpo, usuario_limpo, oficial, confiabilidade))
            row = cur.fetchone()
            colunas = [desc.name for desc in cur.description]
        conn.commit()
    return dict(zip(colunas, row, strict=True))
