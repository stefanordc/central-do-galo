from __future__ import annotations

import base64
import binascii
import re
from datetime import date, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from app.db.pool import pool

BRASILIA_TZ = ZoneInfo("America/Sao_Paulo")
MAX_FOTO_BYTES = 6 * 1024 * 1024
POSICOES_ELENCO = (
    "Goleiro",
    "Lateral-Direito",
    "Lateral-Esquerdo",
    "Zagueiro",
    "Volante",
    "Meia",
    "Atacante",
    "Técnico",
)

DATA_URL_RE = re.compile(
    r"^data:(image/(?:png|jpeg|jpg|webp));base64,(.+)$",
    flags=re.IGNORECASE | re.DOTALL,
)


def _idade(nascimento: date) -> int:
    hoje = datetime.now(BRASILIA_TZ).date()
    return hoje.year - nascimento.year - (
        (hoje.month, hoje.day) < (nascimento.month, nascimento.day)
    )


def _foto_data_url_para_bytes(valor: str | None) -> tuple[str | None, bytes | None]:
    if not valor:
        return None, None

    match = DATA_URL_RE.match(valor.strip())
    if not match:
        raise ValueError("A foto precisa ser uma imagem PNG, JPEG ou WEBP.")

    mime = match.group(1).lower()
    if mime == "image/jpg":
        mime = "image/jpeg"

    try:
        conteudo = base64.b64decode(match.group(2), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Não foi possível interpretar a imagem colada.") from exc

    if not conteudo:
        raise ValueError("A foto colada está vazia.")

    if len(conteudo) > MAX_FOTO_BYTES:
        raise ValueError("A foto é muito grande. Use uma imagem com até 6 MB.")

    return mime, conteudo


def _serializar(row: dict[str, Any]) -> dict[str, Any]:
    nascimento = row.get("nascimento")
    jogador_id = str(row["id"])
    tem_foto = bool(row.get("tem_foto"))
    foto_url_externa = row.get("foto_url")

    return {
        "id": jogador_id,
        "nome_completo": row.get("nome_completo") or "",
        "nome_guerra": row.get("nome") or "",
        "nascimento": nascimento.isoformat() if isinstance(nascimento, date) else None,
        "idade": _idade(nascimento) if isinstance(nascimento, date) else None,
        "numero": row.get("numero"),
        "posicao": row.get("posicao") or "",
        "nacionalidade": row.get("nacionalidade") or "Brasil",
        "ativo": bool(row.get("ativo", True)),
        "tem_foto": tem_foto,
        "foto_url": (
            f"/backend/api/elenco/{jogador_id}/foto?v={int(row.get('atualizado_em').timestamp()) if row.get('atualizado_em') else 1}"
            if tem_foto
            else foto_url_externa
        ),
        "criado_em": row.get("criado_em"),
        "atualizado_em": row.get("atualizado_em"),
    }


def _listar(*, somente_ativos: bool) -> list[dict[str, Any]]:
    where = "where ativo = true" if somente_ativos else ""
    sql = f"""
        select
            id,
            nome,
            nome_completo,
            nascimento,
            numero,
            posicao,
            nacionalidade,
            foto_url,
            foto_bytes is not null as tem_foto,
            ativo,
            criado_em,
            atualizado_em
        from public.jogadores
        {where}
        order by
            case posicao
                when 'Goleiro' then 1
                when 'Lateral-Direito' then 2
                when 'Lateral-Esquerdo' then 3
                when 'Zagueiro' then 4
                when 'Volante' then 5
                when 'Meia' then 6
                when 'Atacante' then 7
                when 'Técnico' then 8
                else 99
            end,
            numero asc nulls last,
            nome asc
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            colunas = [desc.name for desc in cur.description]
            rows = [dict(zip(colunas, row, strict=True)) for row in cur.fetchall()]

    return [_serializar(row) for row in rows]


def listar_elenco_publico() -> list[dict[str, Any]]:
    return _listar(somente_ativos=True)


def listar_elenco_admin() -> list[dict[str, Any]]:
    return _listar(somente_ativos=False)


def criar_jogador(
    *,
    nome_completo: str,
    nome_guerra: str,
    nascimento: date,
    numero: int | None,
    posicao: str,
    nacionalidade: str = "Brasil",
    foto_data_url: str | None = None,
) -> dict[str, Any]:
    nome_completo = nome_completo.strip()
    nome_guerra = nome_guerra.strip()
    posicao = posicao.strip()
    nacionalidade = (nacionalidade or "Brasil").strip()

    if not nome_completo:
        raise ValueError("Informe o nome completo do jogador.")
    if not nome_guerra:
        raise ValueError("Informe o nome de guerra do jogador.")
    if nascimento > datetime.now(BRASILIA_TZ).date():
        raise ValueError("A data de nascimento não pode estar no futuro.")
    if not nacionalidade:
        raise ValueError("Informe a nacionalidade do jogador.")
    if posicao not in POSICOES_ELENCO:
        raise ValueError("Selecione uma posição válida para o elenco.")
    if posicao == "Técnico":
        numero = None
    elif numero is None or not 0 <= int(numero) <= 999:
        raise ValueError("Informe um número de camisa válido para o jogador.")

    foto_mime, foto_bytes = _foto_data_url_para_bytes(foto_data_url)

    sql = """
        insert into public.jogadores (
            nome,
            nome_completo,
            nascimento,
            numero,
            posicao,
            nacionalidade,
            foto_mime,
            foto_bytes,
            ativo,
            atualizado_em
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, true, now())
        returning
            id,
            nome,
            nome_completo,
            nascimento,
            numero,
            posicao,
            nacionalidade,
            foto_url,
            foto_bytes is not null as tem_foto,
            ativo,
            criado_em,
            atualizado_em
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    nome_guerra,
                    nome_completo,
                    nascimento,
                    numero,
                    posicao,
                    nacionalidade,
                    foto_mime,
                    foto_bytes,
                ),
            )
            row = cur.fetchone()
            colunas = [desc.name for desc in cur.description]
        conn.commit()

    return _serializar(dict(zip(colunas, row, strict=True)))


def atualizar_jogador(
    jogador_id: UUID,
    *,
    nome_completo: str,
    nome_guerra: str,
    nascimento: date,
    numero: int | None,
    posicao: str,
    nacionalidade: str = "Brasil",
    foto_data_url: str | None = None,
    remover_foto: bool = False,
) -> dict[str, Any]:
    nome_completo = nome_completo.strip()
    nome_guerra = nome_guerra.strip()
    posicao = posicao.strip()
    nacionalidade = (nacionalidade or "Brasil").strip()

    if not nome_completo:
        raise ValueError("Informe o nome completo do jogador.")
    if not nome_guerra:
        raise ValueError("Informe o nome de guerra do jogador.")
    if nascimento > datetime.now(BRASILIA_TZ).date():
        raise ValueError("A data de nascimento não pode estar no futuro.")
    if not nacionalidade:
        raise ValueError("Informe a nacionalidade do jogador.")
    if posicao not in POSICOES_ELENCO:
        raise ValueError("Selecione uma posição válida para o elenco.")
    if posicao == "Técnico":
        numero = None
    elif numero is None or not 0 <= int(numero) <= 999:
        raise ValueError("Informe um número de camisa válido para o jogador.")

    foto_mime: str | None = None
    foto_bytes: bytes | None = None
    atualizar_foto = False

    if remover_foto:
        atualizar_foto = True
    elif foto_data_url:
        foto_mime, foto_bytes = _foto_data_url_para_bytes(foto_data_url)
        atualizar_foto = True

    if atualizar_foto:
        sql = """
            update public.jogadores
            set nome = %s,
                nome_completo = %s,
                nascimento = %s,
                numero = %s,
                posicao = %s,
                nacionalidade = %s,
                foto_mime = %s,
                foto_bytes = %s,
                foto_url = case when %s then null else foto_url end,
                ativo = true,
                atualizado_em = now()
            where id = %s
            returning
                id,
                nome,
                nome_completo,
                nascimento,
                numero,
                posicao,
                nacionalidade,
                foto_url,
                foto_bytes is not null as tem_foto,
                ativo,
                criado_em,
                atualizado_em
        """
        params = (
            nome_guerra,
            nome_completo,
            nascimento,
            numero,
            posicao,
            nacionalidade,
            foto_mime,
            foto_bytes,
            remover_foto,
            jogador_id,
        )
    else:
        sql = """
            update public.jogadores
            set nome = %s,
                nome_completo = %s,
                nascimento = %s,
                numero = %s,
                posicao = %s,
                nacionalidade = %s,
                ativo = true,
                atualizado_em = now()
            where id = %s
            returning
                id,
                nome,
                nome_completo,
                nascimento,
                numero,
                posicao,
                nacionalidade,
                foto_url,
                foto_bytes is not null as tem_foto,
                ativo,
                criado_em,
                atualizado_em
        """
        params = (
            nome_guerra,
            nome_completo,
            nascimento,
            numero,
            posicao,
            nacionalidade,
            jogador_id,
        )

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if row is None:
                raise LookupError("Jogador não encontrado.")
            colunas = [desc.name for desc in cur.description]
        conn.commit()

    return _serializar(dict(zip(colunas, row, strict=True)))


def excluir_jogador(jogador_id: UUID) -> None:
    sql = "delete from public.jogadores where id = %s returning id"

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (jogador_id,))
            row = cur.fetchone()
            if row is None:
                raise LookupError("Jogador não encontrado.")
        conn.commit()


def obter_foto_jogador(jogador_id: UUID) -> tuple[str, bytes] | None:
    sql = """
        select foto_mime, foto_bytes
        from public.jogadores
        where id = %s
          and foto_bytes is not null
        limit 1
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (jogador_id,))
            row = cur.fetchone()

    if not row:
        return None

    mime = row[0] or "image/jpeg"
    conteudo = bytes(row[1])
    return mime, conteudo
