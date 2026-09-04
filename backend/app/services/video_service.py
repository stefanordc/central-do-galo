from __future__ import annotations

import json
import logging
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

from app.core.config import get_settings
from app.db.pool import pool

logger = logging.getLogger("central_galo.youtube")
settings = get_settings()

BACKEND_DIR = Path(__file__).resolve().parents[2]
TIPOS_VALIDOS = {"video", "short", "live"}
DIAS_INATIVIDADE_TIPO_YOUTUBE = 60

FILTROS_ESPECIAIS_YOUTUBE: dict[str, dict[str, list[str]]] = {
    "youtube-getv": {
        "incluir": ["Atlético-MG", "Galo"],
        "excluir": ["Atlético Madrid", "Atlético de Madrid", "LaLiga"],
    },
    "youtube-espnbrasil": {
        "incluir": ["Atlético-MG", "Galo"],
        "excluir": ["Atlético Madrid", "Atlético de Madrid", "LaLiga"],
    },
    "youtube-cazetv": {
        "incluir": ["Atlético-MG", "Galo"],
        "excluir": ["Atlético Madrid", "Atlético de Madrid", "LaLiga"],
    },
}

VIDEO_FEED_CACHE_TTL_SECONDS = 30.0
_VIDEO_FEED_CACHE: dict[int, tuple[float, dict[str, Any]]] = {}


def _invalidar_video_feed_cache() -> None:
    _VIDEO_FEED_CACHE.clear()


LIVE_STATUS_CACHE_TTL_SECONDS = 60.0
_LIVE_STATUS_CACHE: dict[str, tuple[float, str | None]] = {}


def _extrair_objeto_json_html(html: str, marcador: str) -> dict[str, Any] | None:
    indice_marcador = html.find(marcador)
    if indice_marcador < 0:
        return None

    inicio = html.find("{", indice_marcador)
    if inicio < 0:
        return None

    profundidade = 0
    em_string = False
    escape = False

    for indice in range(inicio, len(html)):
        caractere = html[indice]

        if em_string:
            if escape:
                escape = False
            elif caractere == "\\":
                escape = True
            elif caractere == '"':
                em_string = False
            continue

        if caractere == '"':
            em_string = True
            continue

        if caractere == "{":
            profundidade += 1
        elif caractere == "}":
            profundidade -= 1
            if profundidade == 0:
                trecho = html[inicio:indice + 1]
                try:
                    valor = json.loads(trecho)
                except json.JSONDecodeError:
                    return None
                return valor if isinstance(valor, dict) else None

    return None


def _status_live_player_response(player: dict[str, Any]) -> str | None:
    video_details = player.get("videoDetails")
    if not isinstance(video_details, dict):
        video_details = {}

    microformat = player.get("microformat")
    if not isinstance(microformat, dict):
        microformat = {}

    renderer = microformat.get("playerMicroformatRenderer")
    if not isinstance(renderer, dict):
        renderer = {}

    live_details = renderer.get("liveBroadcastDetails")
    if not isinstance(live_details, dict):
        live_details = {}

    if live_details.get("isLiveNow") is True:
        return "is_live"

    agora = datetime.now(UTC)

    inicio_texto = live_details.get("startTimestamp")
    fim_texto = live_details.get("endTimestamp")

    inicio: datetime | None = None
    if isinstance(inicio_texto, str) and inicio_texto:
        try:
            inicio = datetime.fromisoformat(inicio_texto.replace("Z", "+00:00"))
        except ValueError:
            inicio = None

    if inicio is not None and inicio > agora and not fim_texto:
        return "is_upcoming"

    playability = player.get("playabilityStatus")
    if not isinstance(playability, dict):
        playability = {}

    reason = str(playability.get("reason") or "").lower()
    if "will begin" in reason or "começará" in reason or "comecara" in reason:
        return "is_upcoming"

    if fim_texto:
        return "was_live"

    if video_details.get("isLiveContent") is True:
        return "was_live"

    return None


def _consultar_data_publicacao_youtube(video_id: str) -> datetime | None:
    url = f"https://www.youtube.com/watch?v={video_id}"
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )

    try:
        with urlopen(request, timeout=6) as response:
            html = response.read().decode("utf-8", errors="ignore")

        player = _extrair_objeto_json_html(html, "ytInitialPlayerResponse")
        if not isinstance(player, dict):
            return None

        microformat = player.get("microformat")
        if not isinstance(microformat, dict):
            return None

        renderer = microformat.get("playerMicroformatRenderer")
        if not isinstance(renderer, dict):
            return None

        data_texto = renderer.get("publishDate") or renderer.get("uploadDate")
        if not isinstance(data_texto, str) or not data_texto.strip():
            return None

        data_texto = data_texto.strip()

        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", data_texto):
            return datetime.fromisoformat(data_texto).replace(tzinfo=UTC)

        return datetime.fromisoformat(data_texto.replace("Z", "+00:00"))

    except Exception as exc:
        logger.debug(
            "[YouTube] não foi possível obter data de publicação de %s: %s",
            video_id,
            exc,
        )
        return None


def _atualizar_ultima_publicacao_tipo(
    fonte_id: UUID,
    tipo: str,
    data_publicacao: datetime,
) -> None:
    chave = f"ultima_publicacao_{tipo}"

    sql = """
        update public.fontes
        set configuracao = jsonb_set(
            coalesce(configuracao, '{}'::jsonb),
            %s,
            to_jsonb(%s::text),
            true
        )
        where id = %s
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    [chave],
                    data_publicacao.astimezone(UTC).isoformat(),
                    fonte_id,
                ),
            )
        conn.commit()


def _registrar_ultima_publicacao_tipo(
    fonte_id: UUID,
    tipo: str,
    items: list[dict[str, Any]],
) -> None:
    if not items:
        return

    # A coleta mantém a ordem da aba do YouTube:
    # ordem_na_aba=1 representa o conteúdo mais recente.
    item_mais_recente = min(
        items,
        key=lambda item: int(
            (item.get("metadados") or {}).get("ordem_na_aba") or 999999
        ),
    )

    data_publicacao = item_mais_recente.get("publicado_em")

    if isinstance(data_publicacao, str):
        try:
            data_publicacao = datetime.fromisoformat(
                data_publicacao.replace("Z", "+00:00")
            )
        except ValueError:
            data_publicacao = None

    if not isinstance(data_publicacao, datetime):
        video_id = str(item_mais_recente.get("video_id") or "").strip()
        if video_id:
            data_publicacao = _consultar_data_publicacao_youtube(video_id)

    if isinstance(data_publicacao, datetime):
        if data_publicacao.tzinfo is None:
            data_publicacao = data_publicacao.replace(tzinfo=UTC)

        _atualizar_ultima_publicacao_tipo(
            fonte_id,
            tipo,
            data_publicacao,
        )


def _consultar_status_live_atual(video_id: str) -> str | None:
    agora_monotonic = time.monotonic()
    cache = _LIVE_STATUS_CACHE.get(video_id)

    if cache and agora_monotonic - cache[0] < LIVE_STATUS_CACHE_TTL_SECONDS:
        return cache[1]

    url = f"https://www.youtube.com/watch?v={video_id}"
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/152.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        },
    )

    status_atual: str | None = None

    try:
        with urlopen(request, timeout=5) as response:
            html = response.read().decode("utf-8", errors="ignore")

        player = _extrair_objeto_json_html(html, "ytInitialPlayerResponse")
        if player is not None:
            status_atual = _status_live_player_response(player)
    except Exception as exc:
        logger.debug("[YouTube] não foi possível validar live %s em tempo real: %s", video_id, exc)

    _LIVE_STATUS_CACHE[video_id] = (agora_monotonic, status_atual)
    return status_atual


def _atualizar_status_lives(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return rows

    indices_para_validar: list[int] = []
    video_ids_para_validar: list[str] = []

    for indice, row in enumerate(rows):
        metadados = row.get("metadados")
        if not isinstance(metadados, dict):
            metadados = {}
            row["metadados"] = metadados

        status_salvo = str(metadados.get("live_status") or "")

        # Transmissões já encerradas não precisam ser consultadas novamente.
        # Validamos apenas lives ativas, futuras ou registros sem status.
        if status_salvo != "was_live":
            video_id = str(row.get("video_id") or "").strip()
            if video_id:
                indices_para_validar.append(indice)
                video_ids_para_validar.append(video_id)

    if video_ids_para_validar:
        with ThreadPoolExecutor(max_workers=min(4, len(video_ids_para_validar))) as executor:
            statuses = list(executor.map(_consultar_status_live_atual, video_ids_para_validar))

        for indice, status_atual in zip(indices_para_validar, statuses, strict=True):
            if not status_atual:
                continue

            metadados = rows[indice]["metadados"]
            metadados["live_status"] = status_atual
            metadados["live_status_verificado_em"] = datetime.now(UTC).isoformat()

    prioridade = {
        "is_live": 0,
        "is_upcoming": 1,
        "was_live": 2,
    }

    rows.sort(
        key=lambda row: prioridade.get(
            str((row.get("metadados") or {}).get("live_status") or ""),
            3,
        )
    )

    return rows


def _status_live_card(duration_text: str, metadata_text: str) -> str:
    duracao = duration_text.strip().lower()
    metadata = metadata_text.strip().lower()

    if "ao vivo" in duracao or duracao in {"live", "live now"}:
        return "is_live"

    if any(
        termo in duracao
        for termo in ("em breve", "upcoming", "premiere", "estreia")
    ):
        return "is_upcoming"

    if any(
        termo in metadata
        for termo in ("programado para", "agendado para", "scheduled for", "estreia em")
    ):
        return "is_upcoming"

    return "was_live"


class YoutubeScrapeError(RuntimeError):
    pass


def _normalizar_texto_filtro(valor: str) -> str:
    normalizado = unicodedata.normalize("NFD", valor)
    sem_acentos = "".join(
        caractere
        for caractere in normalizado
        if unicodedata.category(caractere) != "Mn"
    )
    return sem_acentos.casefold()


def _normalizar_lista_termos(termos: list[str]) -> list[str]:
    return [
        _normalizar_texto_filtro(termo.strip())
        for termo in termos
        if isinstance(termo, str) and termo.strip()
    ]


def _titulo_passa_no_filtro(
    titulo: str,
    termos_incluir: list[str],
    termos_excluir: list[str],
) -> bool:
    titulo_normalizado = _normalizar_texto_filtro(titulo)
    inclusoes = _normalizar_lista_termos(termos_incluir)
    exclusoes = _normalizar_lista_termos(termos_excluir)

    # A exclusão sempre tem prioridade.
    if any(termo in titulo_normalizado for termo in exclusoes):
        return False

    if not inclusoes:
        return True

    return any(termo in titulo_normalizado for termo in inclusoes)


def _filtrar_itens_por_termos(
    items: list[dict[str, Any]],
    termos_incluir: list[str],
    termos_excluir: list[str],
) -> list[dict[str, Any]]:
    return [
        item
        for item in items
        if _titulo_passa_no_filtro(
            str(item.get("titulo") or ""),
            termos_incluir,
            termos_excluir,
        )
    ]


def _desativar_videos_fora_do_filtro(
    fonte_id: UUID,
    termos_incluir: list[str],
    termos_excluir: list[str],
) -> int:
    if not termos_incluir and not termos_excluir:
        return 0

    sql_select = """
        select id, titulo
        from public.videos
        where fonte_id = %s
          and ativo = true
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_select, (fonte_id,))
            rows = cur.fetchall()

            ids_desativar: list[UUID] = []
            for video_id, titulo in rows:
                if not _titulo_passa_no_filtro(
                    str(titulo or ""),
                    termos_incluir,
                    termos_excluir,
                ):
                    ids_desativar.append(video_id)

            if not ids_desativar:
                return 0

            cur.execute(
                """
                update public.videos
                set ativo = false
                where id = any(%s)
                """,
                (ids_desativar,),
            )
            total = cur.rowcount

        conn.commit()

    return total


def listar_fontes_youtube() -> list[dict]:
    sql = """
        select id, nome, slug, url_base, confiabilidade, oficial, configuracao
        from public.fontes
        where ativo = true
          and tipo = 'youtube'
          and coalesce(configuracao->>'plataforma', 'youtube') = 'youtube'
        order by oficial desc, confiabilidade desc, nome
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            columns = [desc.name for desc in cur.description]
            return [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]


def salvar_video(
    *,
    fonte_id: UUID,
    video_id: str,
    titulo: str,
    url: str,
    thumbnail_url: str | None,
    descricao: str | None,
    tipo: str,
    publicado_em: datetime | None,
    metadados: dict[str, Any],
) -> UUID:
    if tipo not in TIPOS_VALIDOS:
        tipo = "video"

    sql = """
        insert into public.videos (
            fonte_id,
            video_id,
            titulo,
            url,
            thumbnail_url,
            descricao,
            tipo,
            publicado_em,
            metadados,
            ativo
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, true)
        on conflict (video_id) do update
        set titulo = excluded.titulo,
            url = excluded.url,
            thumbnail_url = coalesce(excluded.thumbnail_url, public.videos.thumbnail_url),
            descricao = coalesce(excluded.descricao, public.videos.descricao),
            tipo = excluded.tipo,
            publicado_em = coalesce(excluded.publicado_em, public.videos.publicado_em),
            coletado_em = now(),
            metadados = excluded.metadados,
            ativo = true
        returning id
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    fonte_id,
                    video_id,
                    titulo,
                    url,
                    thumbnail_url,
                    descricao,
                    tipo,
                    publicado_em,
                    json.dumps(metadados, ensure_ascii=False),
                ),
            )
            row = cur.fetchone()
        conn.commit()

    return row[0]


def _serializar_video(data: dict[str, Any]) -> dict[str, Any]:
    for key in ("id", "fonte_id"):
        value = data.get(key)
        if value is not None:
            data[key] = str(value)

    for key in ("publicado_em", "coletado_em"):
        value = data.get(key)
        if isinstance(value, datetime):
            data[key] = value.isoformat()

    if not isinstance(data.get("metadados"), dict):
        data["metadados"] = {}

    return data


def listar_videos(
    *,
    tipo: str | None = None,
    limit: int = 10,
    offset: int = 0,
    fonte: str | None = None,
) -> list[dict]:
    filtros: list[str] = ["v.ativo = true", "f.ativo = true", "f.tipo = 'youtube'"]
    params: list[Any] = []

    if tipo:
        filtros.append("v.tipo = %s")
        params.append(tipo)

    if fonte:
        filtros.append("f.slug = %s")
        params.append(fonte)

    params.extend([limit, offset])

    sql = f"""
        select
            v.id,
            v.video_id,
            v.titulo,
            v.url,
            v.thumbnail_url,
            v.descricao,
            v.tipo,
            v.publicado_em,
            v.coletado_em,
            v.metadados,
            f.id as fonte_id,
            f.nome as fonte_nome,
            f.slug as fonte_slug,
            f.oficial as fonte_oficial
        from public.videos v
        join public.fontes f on f.id = v.fonte_id
        where {' and '.join(filtros)}
        order by
            coalesce(v.publicado_em, v.coletado_em) desc,
            case
                when (v.metadados->>'ordem_na_aba') ~ '^\\d+$'
                then (v.metadados->>'ordem_na_aba')::integer
                else 9999
            end asc,
            v.coletado_em desc
        limit %s offset %s
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, tuple(params))
            columns = [desc.name for desc in cur.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]

    return [_serializar_video(row) for row in rows]


def listar_feed_videos_cacheado(*, limit_por_canal: int = 13) -> dict[str, Any]:
    limit_por_canal = max(1, min(limit_por_canal, 50))

    agora = time.monotonic()
    cache = _VIDEO_FEED_CACHE.get(limit_por_canal)
    if cache and agora - cache[0] < VIDEO_FEED_CACHE_TTL_SECONDS:
        return cache[1]

    sql = """
        with atividade as (
            select
                f.id as fonte_id,
                t.tipo,
                max(v.publicado_em) filter (
                    where v.ativo = true and v.tipo = t.tipo
                ) as ultima_publicacao_banco,
                case
                    when t.tipo = 'video'
                        then nullif(f.configuracao->>'ultima_publicacao_video', '')::timestamptz
                    when t.tipo = 'short'
                        then nullif(f.configuracao->>'ultima_publicacao_short', '')::timestamptz
                    when t.tipo = 'live'
                        then nullif(f.configuracao->>'ultima_publicacao_live', '')::timestamptz
                    else null
                end as ultima_publicacao_config
            from public.fontes f
            cross join (
                values ('video'), ('short'), ('live')
            ) as t(tipo)
            left join public.videos v
                on v.fonte_id = f.id
               and v.tipo = t.tipo
            where f.ativo = true
              and f.tipo = 'youtube'
            group by
                f.id,
                f.configuracao,
                t.tipo
        ),
        tipos_recentes as (
            select
                fonte_id,
                tipo
            from atividade
            where coalesce(
                ultima_publicacao_config,
                ultima_publicacao_banco,
                case
                    when tipo = 'short' then now()
                    else null
                end
            ) >= now() - (%s || ' days')::interval
        ),
        ranqueados as (
            select
                v.id,
                v.video_id,
                v.titulo,
                v.url,
                v.thumbnail_url,
                v.descricao,
                v.tipo,
                v.publicado_em,
                v.coletado_em,
                v.metadados,
                f.id as fonte_id,
                f.nome as fonte_nome,
                f.slug as fonte_slug,
                f.oficial as fonte_oficial,
                row_number() over (
                    partition by v.fonte_id, v.tipo
                    order by
                        coalesce(v.publicado_em, v.coletado_em) desc,
                        v.coletado_em desc
                ) as posicao
            from public.videos v
            join public.fontes f on f.id = v.fonte_id
            join tipos_recentes tr
              on tr.fonte_id = v.fonte_id
             and tr.tipo = v.tipo
            where v.ativo = true
              and f.ativo = true
              and f.tipo = 'youtube'
        )
        select
            id,
            video_id,
            titulo,
            url,
            thumbnail_url,
            descricao,
            tipo,
            publicado_em,
            coletado_em,
            metadados,
            fonte_id,
            fonte_nome,
            fonte_slug,
            fonte_oficial
        from ranqueados
        where posicao <= %s
        order by coalesce(publicado_em, coletado_em) desc, coletado_em desc
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    DIAS_INATIVIDADE_TIPO_YOUTUBE,
                    limit_por_canal,
                ),
            )
            columns = [desc.name for desc in cur.description]
            rows = [dict(zip(columns, row, strict=True)) for row in cur.fetchall()]

    itens = [_serializar_video(row) for row in rows]

    videos = [item for item in itens if item.get("tipo") == "video"]
    shorts = [item for item in itens if item.get("tipo") == "short"]
    lives = [item for item in itens if item.get("tipo") == "live"]

    prioridade_live = {
        "is_live": 0,
        "is_upcoming": 1,
        "was_live": 2,
    }

    def chave_live(item: dict[str, Any]) -> tuple[int, float]:
        status = str((item.get("metadados") or {}).get("live_status") or "")
        data_texto = str(item.get("publicado_em") or item.get("coletado_em") or "")
        try:
            timestamp = datetime.fromisoformat(data_texto.replace("Z", "+00:00")).timestamp()
        except ValueError:
            timestamp = 0.0
        return (prioridade_live.get(status, 3), -timestamp)

    lives.sort(key=chave_live)

    ultima_coleta = None
    datas = [
        str(item.get("coletado_em"))
        for item in itens
        if item.get("coletado_em")
    ]
    if datas:
        ultima_coleta = max(datas)

    resultado: dict[str, Any] = {
        "videos": videos,
        "shorts": shorts,
        "lives": lives,
        "ultima_coleta": ultima_coleta,
        "limit_por_canal": limit_por_canal,
    }

    _VIDEO_FEED_CACHE[limit_por_canal] = (agora, resultado)
    return resultado


def status_videos() -> dict:
    sql = """
        select
            count(*) filter (where v.ativo = true) as total,
            count(*) filter (where v.ativo = true and v.tipo = 'video') as videos,
            count(*) filter (where v.ativo = true and v.tipo = 'short') as shorts,
            count(*) filter (where v.ativo = true and v.tipo = 'live') as lives,
            max(v.coletado_em) as ultima_coleta
        from public.videos v
        join public.fontes f on f.id = v.fonte_id
        where f.ativo = true
          and f.tipo = 'youtube'
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            columns = [desc.name for desc in cur.description]
            data = dict(zip(columns, row, strict=True))

    if isinstance(data.get("ultima_coleta"), datetime):
        data["ultima_coleta"] = data["ultima_coleta"].isoformat()

    data["job_habilitado"] = settings.youtube_sync_enabled
    data["intervalo_segundos"] = settings.youtube_sync_interval_seconds
    data["itens_por_secao"] = settings.youtube_items_per_section
    data["coletor"] = "seleniumbase_uc_publico"
    return data


def _duration_seconds(texto: str | None) -> int | None:
    if not texto:
        return None
    texto = texto.strip()
    if not re.fullmatch(r"\d{1,2}:\d{2}(?::\d{2})?", texto):
        return None
    partes = [int(parte) for parte in texto.split(":")]
    if len(partes) == 2:
        return partes[0] * 60 + partes[1]
    return partes[0] * 3600 + partes[1] * 60 + partes[2]


def _publicado_aproximado(metadata_text: str | None) -> datetime | None:
    if not metadata_text:
        return None

    texto = metadata_text.lower().replace("\xa0", " ")
    match = re.search(
        r"(?:há|ha)\s+(\d+)\s+(minuto|minutos|hora|horas|dia|dias|semana|semanas|m[eê]s|meses|ano|anos)",
        texto,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    quantidade = int(match.group(1))
    unidade = match.group(2).lower()
    agora = datetime.now(UTC)

    if unidade.startswith("minuto"):
        return agora - timedelta(minutes=quantidade)
    if unidade.startswith("hora"):
        return agora - timedelta(hours=quantidade)
    if unidade.startswith("dia"):
        return agora - timedelta(days=quantidade)
    if unidade.startswith("semana"):
        return agora - timedelta(weeks=quantidade)
    if unidade in {"mês", "mes", "meses"}:
        return agora - timedelta(days=30 * quantidade)
    if unidade.startswith("ano"):
        return agora - timedelta(days=365 * quantidade)
    return None


def _video_id_from_href(href: str, tipo: str) -> str | None:
    if not href:
        return None

    parsed = urlparse(href if "://" in href else f"https://www.youtube.com{href}")
    path = parsed.path or ""

    if tipo == "short":
        match = re.search(r"/shorts/([A-Za-z0-9_-]{6,})", path)
        return match.group(1) if match else None

    if path == "/watch":
        value = parse_qs(parsed.query).get("v", [None])[0]
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{6,}", value):
            return value
    return None


class YoutubePublicScraper:
    def __init__(self) -> None:
        self.driver: Any | None = None
        debug_dir = Path(settings.youtube_scrape_debug_dir)
        if not debug_dir.is_absolute():
            debug_dir = BACKEND_DIR / debug_dir
        self.debug_dir = debug_dir

    def _driver(self):
        if self.driver is not None:
            return self.driver

        # Usa sempre um perfil temporário e limpo.
        # Isso evita reaproveitar cache, DOM ou estado do canal anterior.
        kwargs: dict[str, Any] = {
            "uc": True,
            "locale_code": "pt-BR",
            "page_load_strategy": "eager",
        }

        if settings.youtube_scrape_headless:
            kwargs["headless2"] = True
        else:
            kwargs["headed"] = True

        self.driver = Driver(**kwargs)

        self.driver.set_page_load_timeout(settings.youtube_scrape_page_timeout_seconds)
        self.driver.set_window_size(1440, 1800)
        return self.driver

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                logger.exception("[YouTube] erro ao encerrar Chrome")
            self.driver = None

    def _aguardar_canal_correto(self, url: str) -> None:
        driver = self._driver()

        match = re.search(r"youtube\.com/(@[^/]+)", url, flags=re.IGNORECASE)
        handle = match.group(1).strip().lower() if match else ""

        if not handle:
            return

        def canal_pronto(d) -> bool:
            try:
                current_url = str(d.current_url or "").lower()

                if f"/{handle}" not in current_url:
                    return False

                return bool(
                    d.execute_script(
                        """
                        const handle = arguments[0].toLowerCase();

                        const canonical =
                          document.querySelector('link[rel="canonical"]')?.href?.toLowerCase() || '';

                        const ogUrl =
                          document.querySelector('meta[property="og:url"]')?.content?.toLowerCase() || '';

                        const vanity =
                          window.ytInitialData?.metadata?.channelMetadataRenderer?.vanityChannelUrl?.toLowerCase?.() || '';

                        const grade =
                          document.querySelector('ytd-rich-grid-renderer, ytd-grid-renderer');

                        const canalConfirmado =
                          canonical.includes('/' + handle) ||
                          ogUrl.includes('/' + handle) ||
                          vanity.includes('/' + handle);

                        return canalConfirmado && Boolean(grade);
                        """,
                        handle,
                    )
                )
            except Exception:
                return False

        WebDriverWait(
            driver,
            settings.youtube_scrape_wait_seconds,
        ).until(canal_pronto)

        # Espera a grade estabilizar antes da leitura.
        ultimo_total = -1
        estavel = 0

        for _ in range(12):
            try:
                total = len(self._cards_dom("video"))
            except Exception:
                total = 0

            if total > 0 and total == ultimo_total:
                estavel += 1
            else:
                estavel = 0

            if estavel >= 2:
                break

            ultimo_total = total
            time.sleep(0.35)

    def _salvar_debug(self, slug: str, tipo: str) -> None:
        if not settings.youtube_scrape_debug_enabled or self.driver is None:
            return

        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            base = self.debug_dir / f"{slug}-{tipo}-{stamp}"
            base.with_suffix(".html").write_text(self.driver.page_source, encoding="utf-8")
            self.driver.save_screenshot(str(base.with_suffix(".png")))
            body_text = self.driver.execute_script("return document.body ? document.body.innerText : ''") or ""
            base.with_suffix(".txt").write_text(str(body_text), encoding="utf-8")
            logger.info("[YouTube] debug salvo em %s.*", base)
        except Exception:
            logger.exception("[YouTube] falha ao salvar debug")

    def _fechar_consentimento(self) -> None:
        if self.driver is None:
            return
        try:
            self.driver.execute_script(
                """
                const textos = ['Aceitar tudo', 'Accept all', 'Rejeitar tudo', 'Reject all'];
                const botoes = Array.from(document.querySelectorAll('button'));
                const botao = botoes.find((item) => textos.includes((item.textContent || '').trim()));
                if (botao) { botao.click(); return true; }
                return false;
                """
            )
        except Exception:
            pass

    def _clicar_publico(self) -> bool:
        driver = self._driver()
        seletor = 'button[role="tab"][aria-label="Público"]'
        try:
            botao = WebDriverWait(driver, settings.youtube_scrape_wait_seconds).until(
                lambda d: d.find_element("css selector", seletor)
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", botao)
            # Clica mesmo quando aria-selected=true. Isso mantém o fluxo explícito
            # e impede que a aba de membros permaneça ativa após mudanças do YouTube.
            driver.execute_script("arguments[0].click();", botao)
            WebDriverWait(driver, settings.youtube_scrape_wait_seconds).until(
                lambda d: d.find_element("css selector", seletor).get_attribute("aria-selected") == "true"
            )
            logger.info("[YouTube] filtro Público selecionado")
            return True
        except Exception as exc:
            logger.warning("[YouTube] botão Público não encontrado/clicável: %s", exc)
            return False

    def _clicar_publico_se_existir(self) -> bool:
        driver = self._driver()
        seletor = 'button[role="tab"][aria-label="Público"]'
        try:
            botoes = driver.find_elements("css selector", seletor)
            if not botoes:
                return False
            botao = botoes[0]
            driver.execute_script("arguments[0].click();", botao)
            logger.info("[YouTube] filtro Público selecionado")
            return True
        except Exception:
            return False

    def _cards_dom(self, tipo: str) -> list[dict[str, Any]]:
        driver = self._driver()
        return driver.execute_script(
            """
            const tipo = arguments[0];

            const root =
              document.querySelector('ytd-rich-grid-renderer') ||
              document.querySelector('ytd-grid-renderer');

            if (!root) return [];

            const containers = Array.from(root.querySelectorAll(
              'ytd-rich-item-renderer, ytm-shorts-lockup-view-model, ytd-grid-video-renderer, yt-lockup-view-model'
            ));

            const saida = [];
            const vistos = new Set();

            function videoId(href) {
              if (!href) return null;

              try {
                const url = new URL(href, location.origin);

                if (tipo === 'short') {
                  const m = url.pathname.match(/\/shorts\/([A-Za-z0-9_-]{6,})/);
                  return m ? m[1] : null;
                }

                if (url.pathname === '/watch') {
                  return url.searchParams.get('v');
                }
              } catch (_) {}

              return null;
            }

            function adicionarCard(card) {
              const links = Array.from(card.querySelectorAll('a[href]'));
              const link = links.find((a) => videoId(a.getAttribute('href')));
              if (!link) return;

              const href = link.href || link.getAttribute('href') || '';
              const id = videoId(href);
              if (!id || vistos.has(id)) return;

              const cardText = (card.innerText || '').trim();
              const lowerText = cardText.toLowerCase();

              if (
                lowerText.includes('só para membros') ||
                lowerText.includes('members only')
              ) {
                return;
              }

              const titleNode = card.querySelector(
                'a.ytLockupMetadataViewModelTitle, #video-title-link, #video-title, h3 a[href]'
              );

              let title = '';
              if (titleNode) {
                title = (
                  titleNode.getAttribute('title') ||
                  titleNode.textContent ||
                  ''
                ).trim();
              }

              if (!title) {
                title = (
                  link.getAttribute('title') ||
                  link.getAttribute('aria-label') ||
                  ''
                ).trim();
              }

              if (!title) return;

              const img = card.querySelector('img[src*="i.ytimg.com"]');
              const thumb = img
                ? (img.currentSrc || img.src || img.getAttribute('src') || '')
                : '';

              const badge = card.querySelector(
                'yt-thumbnail-badge-view-model .ytBadgeShapeText, ytd-thumbnail-overlay-time-status-renderer #text, badge-shape .ytBadgeShapeText'
              );
              const durationText = badge
                ? (badge.textContent || '').trim()
                : '';

              const metadataNodes = Array.from(card.querySelectorAll(
                '.ytContentMetadataViewModelMetadataText, #metadata-line span, ytd-video-meta-block #metadata-line span'
              ));

              const metadataText = metadataNodes
                .map((node) => (node.textContent || '').trim())
                .filter(Boolean)
                .join(' • ');

              vistos.add(id);

              saida.push({
                video_id: id,
                href,
                titulo: title,
                thumbnail_url: thumb,
                duration_text: durationText,
                metadata_text: metadataText,
                card_text: cardText,
              });
            }

            for (const card of containers) {
              adicionarCard(card);
            }

            // Fallback também restrito à grade do canal.
            if (!saida.length) {
              const anchors = Array.from(
                root.querySelectorAll(
                  'a[href*="/watch?v="], a[href*="/shorts/"]'
                )
              );

              for (const link of anchors) {
                const href = link.href || link.getAttribute('href') || '';
                const id = videoId(href);

                if (!id || vistos.has(id)) continue;

                const title = (
                  link.getAttribute('title') ||
                  link.getAttribute('aria-label') ||
                  link.textContent ||
                  ''
                ).trim();

                if (!title) continue;

                vistos.add(id);

                saida.push({
                  video_id: id,
                  href,
                  titulo: title,
                  thumbnail_url: '',
                  duration_text: '',
                  metadata_text: '',
                  card_text: '',
                });
              }
            }

            return saida;
            """,
            tipo,
        ) or []

    def coletar_aba(self, url: str, *, tipo: str, limite: int, slug: str) -> list[dict[str, Any]]:
        driver = self._driver()
        logger.info("[YouTube] GET %s", url)
        driver.get(url)
        self._fechar_consentimento()
        self._aguardar_canal_correto(url)

        # Fluxo pedido para a aba de vídeos: escolher explicitamente o filtro Público.
        # Nas outras abas, usa o mesmo filtro somente se ele existir no DOM.
        if tipo == "video":
            if slug == "youtube-canaldofrossard":
                self._clicar_publico_se_existir()
            else:
                self._clicar_publico()
        else:
            self._clicar_publico_se_existir()

        try:
            WebDriverWait(driver, settings.youtube_scrape_wait_seconds).until(
                lambda _: len(self._cards_dom(tipo)) > 0
            )
        except Exception:
            self._salvar_debug(slug, tipo)
            raise YoutubeScrapeError(
                f"Nenhum card público do YouTube foi encontrado na aba {tipo}."
            )

        encontrados: dict[str, dict[str, Any]] = {}
        for tentativa in range(settings.youtube_scrape_max_scrolls + 1):
            cards = self._cards_dom(tipo)
            for card in cards:
                video_id = str(card.get("video_id") or "").strip()
                if video_id and video_id not in encontrados:
                    encontrados[video_id] = card
                if len(encontrados) >= limite:
                    break

            logger.info(
                "[YouTube] %s | tentativa=%s | encontrados=%s",
                tipo,
                tentativa + 1,
                len(encontrados),
            )
            if len(encontrados) >= limite:
                break

            driver.execute_script(
                "window.scrollBy({top: Math.max(window.innerHeight * 1.4, 1100), behavior: 'instant'});"
            )
            time.sleep(settings.youtube_scrape_scroll_pause_seconds)

        if not encontrados:
            self._salvar_debug(slug, tipo)
            raise YoutubeScrapeError(f"A aba {tipo} abriu, mas nenhum conteúdo público foi extraído.")

        resultado: list[dict[str, Any]] = []
        for ordem, card in enumerate(list(encontrados.values())[:limite], start=1):
            video_id = str(card["video_id"])
            href = str(card.get("href") or "")
            canonical_url = (
                f"https://www.youtube.com/shorts/{video_id}"
                if tipo == "short"
                else f"https://www.youtube.com/watch?v={video_id}"
            )
            thumbnail = str(card.get("thumbnail_url") or "").strip()
            if not thumbnail:
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

            duration_text = str(card.get("duration_text") or "").strip()
            metadata_text = str(card.get("metadata_text") or "").strip()
            publicado_em = _publicado_aproximado(metadata_text)

            metadados: dict[str, Any] = {
                "plataforma": "youtube",
                "origem": "seleniumbase_uc_publico",
                "publico": True,
                "ordem_na_aba": ordem,
                "duration": _duration_seconds(duration_text),
                "duration_text": duration_text or None,
                "metadata_text": metadata_text or None,
                "embed_url": f"https://www.youtube.com/embed/{video_id}",
                "url_extraida": href or canonical_url,
            }

            if tipo == "live":
                metadados["live_status"] = _status_live_card(duration_text, metadata_text)

            metadados = {key: value for key, value in metadados.items() if value is not None}

            resultado.append(
                {
                    "video_id": video_id,
                    "titulo": str(card.get("titulo") or "").strip(),
                    "url": canonical_url,
                    "thumbnail_url": thumbnail,
                    "descricao": None,
                    "tipo": tipo,
                    "publicado_em": publicado_em,
                    "metadados": metadados,
                }
            )

        return resultado


def _desativar_membros_antigos(fonte_id: UUID) -> int:
    sql = """
        update public.videos
        set ativo = false
        where fonte_id = %s
          and ativo = true
          and lower(coalesce(metadados->>'availability', '')) in ('subscriber_only', 'premium_only')
    """
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (fonte_id,))
            total = cur.rowcount
        conn.commit()
    return total


def sincronizar_youtube() -> dict:
    fontes = listar_fontes_youtube()
    total_processados = 0
    total_salvos = 0
    resultados: list[dict[str, Any]] = []

    for fonte in fontes:
        config = fonte.get("configuracao") or {}
        if not isinstance(config, dict):
            config = {}

        _desativar_membros_antigos(fonte["id"])

        abas = [
            ("video", config.get("videos_url")),
            ("short", config.get("shorts_url")),
            ("live", config.get("streams_url")),
        ]

        fonte_resultado = {
            "fonte": fonte["slug"],
            "nome": fonte["nome"],
            "videos": 0,
            "shorts": 0,
            "lives": 0,
            "erros": [],
        }

        ids_encontrados_na_aba_videos: set[str] = set()

        # IMPORTANTE:
        # cada canal usa uma sessão Selenium própria.
        # Isso impede que cards/DOM do canal anterior sejam reaproveitados.
        scraper = YoutubePublicScraper()

        try:
            for tipo, url in abas:
                if not isinstance(url, str) or not url.strip():
                    continue

                filtro_termos = config.get("filtro_termos")
                if not isinstance(filtro_termos, list):
                    filtro_termos = []

                filtro_excluir_termos = config.get("filtro_excluir_termos")
                if not isinstance(filtro_excluir_termos, list):
                    filtro_excluir_termos = []

                regra_especial = FILTROS_ESPECIAIS_YOUTUBE.get(fonte["slug"])
                if regra_especial:
                    filtro_termos = list(regra_especial["incluir"])
                    filtro_excluir_termos = list(regra_especial["excluir"])

                if filtro_termos or filtro_excluir_termos:
                    desativados = _desativar_videos_fora_do_filtro(
                        fonte["id"],
                        filtro_termos,
                        filtro_excluir_termos,
                    )
                    if desativados:
                        logger.info(
                            "[YouTube] %s | desativados por filtro=%s",
                            fonte["slug"],
                            desativados,
                        )

                limite_coleta = max(settings.youtube_items_per_section, 13)
                if filtro_termos or filtro_excluir_termos:
                    # Canais generalistas precisam de uma varredura maior para
                    # encontrarmos publicações específicas do Atlético.
                    limite_coleta = max(settings.youtube_items_per_section * 6, 60)

                try:
                    items = scraper.coletar_aba(
                        url.strip(),
                        tipo=tipo,
                        limite=limite_coleta,
                        slug=fonte["slug"],
                    )
                except Exception as exc:
                    logger.exception("[YouTube] falha em %s (%s): %s", fonte["slug"], tipo, exc)
                    fonte_resultado["erros"].append(f"{tipo}: {exc}")
                    continue

                total_processados += len(items)

                if filtro_termos or filtro_excluir_termos:
                    total_antes_filtro = len(items)
                    items = _filtrar_itens_por_termos(
                        items,
                        filtro_termos,
                        filtro_excluir_termos,
                    )
                    items = items[:settings.youtube_items_per_section]
                    logger.info(
                        "[YouTube] %s | %s | incluir=%s | excluir=%s | encontrados=%s | aceitos=%s",
                        fonte["slug"],
                        tipo,
                        filtro_termos,
                        filtro_excluir_termos,
                        total_antes_filtro,
                        len(items),
                    )

                    if fonte["slug"] == "youtube-getv":
                        for item in items:
                            logger.info(
                                "[YouTube][ge tv] ACEITO | %s",
                                item.get("titulo"),
                            )

                _registrar_ultima_publicacao_tipo(
                    fonte["id"],
                    tipo,
                    items,
                )

                if tipo == "video":
                    ids_encontrados_na_aba_videos.update(
                        str(item.get("video_id") or "")
                        for item in items
                        if item.get("video_id")
                    )

                if tipo == "live" and ids_encontrados_na_aba_videos:
                    items = [
                        item
                        for item in items
                        if str(item.get("video_id") or "") not in ids_encontrados_na_aba_videos
                    ]

                for item in items:
                    salvar_video(fonte_id=fonte["id"], **item)
                    total_salvos += 1

                if tipo == "video":
                    fonte_resultado["videos"] = len(items)
                elif tipo == "short":
                    fonte_resultado["shorts"] = len(items)
                elif tipo == "live":
                    fonte_resultado["lives"] = len(items)

        finally:
            # Fecha completamente o navegador antes de passar ao próximo canal.
            scraper.close()

        resultados.append(fonte_resultado)

    _invalidar_video_feed_cache()

    return {
        "fontes": len(fontes),
        "processados": total_processados,
        "salvos": total_salvos,
        "resultados": resultados,
    }
