from __future__ import annotations

import json
import logging
import os
import time
import unicodedata
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from app.db.pool import pool

logger = logging.getLogger("central_galo.jogos")

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

API_BASE = "https://v3.football.api-sports.io"
TIMEZONE = os.getenv("API_FOOTBALL_TIMEZONE", "America/Sao_Paulo").strip() or "America/Sao_Paulo"

STATUS_FINALIZADOS = {"FT", "AET", "PEN", "AWD", "WO"}
STATUS_AO_VIVO = {"1H", "HT", "2H", "ET", "BT", "P", "LIVE", "INT"}
STATUS_ADIADOS = {"PST", "SUSP", "CANC", "ABD"}

ULTIMA_COTA_RESTANTE: int | None = None
LIMITE_POR_MINUTO: int | None = None


def _normalizar(valor: str | None) -> str:
    texto = unicodedata.normalize("NFKD", valor or "")
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    return " ".join(texto.lower().strip().split())


def _eh_galo_nome(nome: str | None) -> bool:
    valor = _normalizar(nome)
    return (
        valor in {
            "atletico mineiro",
            "atletico-mg",
            "atletico mg",
            "clube atletico mineiro",
        }
        or "atletico mineiro" in valor
    )


def _api_key() -> str:
    chave = os.getenv("API_FOOTBALL_KEY", "").strip()
    if not chave:
        raise RuntimeError(
            "API_FOOTBALL_KEY não configurada. "
            "Adicione a chave da API-Football ao arquivo backend/.env."
        )
    return chave


def _esperar_cota() -> None:
    # Plano gratuito: 10 chamadas/minuto.
    if LIMITE_POR_MINUTO is not None and LIMITE_POR_MINUTO <= 10:
        time.sleep(6.2)
    else:
        time.sleep(0.15)


def _api_get(endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    global ULTIMA_COTA_RESTANTE, LIMITE_POR_MINUTO

    url = f"{API_BASE}{endpoint}"
    headers = {
        "x-apisports-key": _api_key(),
        "Accept": "application/json",
    }

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        response = client.get(url, headers=headers, params=params or {})

    try:
        if response.headers.get("x-ratelimit-requests-remaining") is not None:
            ULTIMA_COTA_RESTANTE = int(response.headers["x-ratelimit-requests-remaining"])
    except (TypeError, ValueError):
        pass

    try:
        if response.headers.get("x-ratelimit-limit") is not None:
            LIMITE_POR_MINUTO = int(response.headers["x-ratelimit-limit"])
        elif response.headers.get("X-RateLimit-Limit") is not None:
            LIMITE_POR_MINUTO = int(response.headers["X-RateLimit-Limit"])
    except (TypeError, ValueError):
        pass

    if response.status_code == 429:
        raise RuntimeError("Limite de requisições da API-Football atingido.")

    response.raise_for_status()

    payload = response.json()
    errors = payload.get("errors")

    if errors:
        if isinstance(errors, dict):
            detalhes = "; ".join(f"{k}: {v}" for k, v in errors.items())
        else:
            detalhes = str(errors)
        raise RuntimeError(f"API-Football retornou erro: {detalhes}")

    dados = payload.get("response") or []
    return dados if isinstance(dados, list) else []


def descobrir_time_galo() -> dict[str, Any]:
    id_configurado = os.getenv("API_FOOTBALL_TEAM_ID", "").strip()

    if id_configurado:
        dados = _api_get("/teams", {"id": id_configurado})
        if dados:
            return dados[0]["team"]

    buscas = ["Atletico Mineiro", "Atletico-MG"]

    for busca in buscas:
        dados = _api_get("/teams", {"search": busca})

        candidatos: list[dict[str, Any]] = []
        for item in dados:
            team = item.get("team") or {}
            nome = str(team.get("name") or "")
            pais = _normalizar(str(team.get("country") or ""))

            if _eh_galo_nome(nome) and pais == "brazil":
                candidatos.append(team)

        if candidatos:
            return candidatos[0]

        _esperar_cota()

    raise RuntimeError(
        "Não foi possível localizar o Atlético-MG na API-Football. "
        "Defina API_FOOTBALL_TEAM_ID no backend/.env."
    )


def _status_interno(status_short: str) -> str:
    status_short = (status_short or "").upper()

    if status_short in STATUS_FINALIZADOS:
        return "finalizado"

    if status_short in STATUS_AO_VIVO:
        return "ao_vivo"

    if status_short in STATUS_ADIADOS:
        return "adiado"

    return "agendado"


def _upsert_competicao(league: dict[str, Any]) -> str | None:
    league_info = league.get("league") or {}
    country = league.get("country") or {}

    league_id = league_info.get("id")
    nome = str(league_info.get("name") or "").strip()
    temporada = str(league.get("season") or "").strip() or None

    if not nome:
        return None

    sql = """
        insert into public.competicoes (
            id_externo,
            nome,
            temporada,
            pais,
            logo_url,
            ativo
        )
        values (
            %(id_externo)s,
            %(nome)s,
            %(temporada)s,
            %(pais)s,
            %(logo_url)s,
            true
        )
        on conflict (nome, temporada) do update
        set id_externo = excluded.id_externo,
            pais = excluded.pais,
            logo_url = excluded.logo_url,
            ativo = true
        returning id
    """

    parametros = {
        "id_externo": f"api-football:{league_id}" if league_id is not None else None,
        "nome": nome,
        "temporada": temporada,
        "pais": country if isinstance(country, str) else country.get("name"),
        "logo_url": league_info.get("logo"),
    }

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            row = cur.fetchone()
        conn.commit()

    return str(row[0]) if row else None


def _metadados_fixture(item: dict[str, Any]) -> dict[str, Any]:
    fixture = item.get("fixture") or {}
    status = fixture.get("status") or {}
    league = item.get("league") or {}
    teams = item.get("teams") or {}

    home = teams.get("home") or {}
    away = teams.get("away") or {}

    return {
        "fonte": "api-football",
        "api_football": {
            "fixture_id": fixture.get("id"),
            "timezone": fixture.get("timezone"),
            "timestamp": fixture.get("timestamp"),
            "referee": fixture.get("referee"),
            "status_short": status.get("short"),
            "status_long": status.get("long"),
            "elapsed": status.get("elapsed"),
            "league_id": league.get("id"),
            "league_name": league.get("name"),
            "league_round": league.get("round"),
            "season": league.get("season"),
            "team_ids": {
                "home": home.get("id"),
                "away": away.get("id"),
            },
        },
    }


def _upsert_jogo(item: dict[str, Any]) -> str | None:
    fixture = item.get("fixture") or {}
    league = item.get("league") or {}
    teams = item.get("teams") or {}
    goals = item.get("goals") or {}

    home = teams.get("home") or {}
    away = teams.get("away") or {}
    venue = fixture.get("venue") or {}
    status_api = fixture.get("status") or {}

    fixture_id = fixture.get("id")
    inicio_em = fixture.get("date")

    if fixture_id is None or not inicio_em:
        return None

    competicao_id = _upsert_competicao(
        {
            "league": {
                "id": league.get("id"),
                "name": league.get("name"),
                "logo": league.get("logo"),
            },
            "country": league.get("country"),
            "season": league.get("season"),
        }
    )

    metadados = _metadados_fixture(item)

    sql = """
        insert into public.jogos (
            id_externo,
            competicao_id,
            rodada,
            mandante,
            visitante,
            mandante_logo_url,
            visitante_logo_url,
            inicio_em,
            estadio,
            cidade,
            status,
            gols_mandante,
            gols_visitante,
            metadados,
            atualizado_em
        )
        values (
            %(id_externo)s,
            %(competicao_id)s,
            %(rodada)s,
            %(mandante)s,
            %(visitante)s,
            %(mandante_logo_url)s,
            %(visitante_logo_url)s,
            %(inicio_em)s,
            %(estadio)s,
            %(cidade)s,
            %(status)s,
            %(gols_mandante)s,
            %(gols_visitante)s,
            %(metadados)s::jsonb,
            now()
        )
        on conflict (id_externo) do update
        set competicao_id = excluded.competicao_id,
            rodada = excluded.rodada,
            mandante = excluded.mandante,
            visitante = excluded.visitante,
            mandante_logo_url = excluded.mandante_logo_url,
            visitante_logo_url = excluded.visitante_logo_url,
            inicio_em = excluded.inicio_em,
            estadio = excluded.estadio,
            cidade = excluded.cidade,
            status = excluded.status,
            gols_mandante = excluded.gols_mandante,
            gols_visitante = excluded.gols_visitante,
            metadados = coalesce(public.jogos.metadados, '{}'::jsonb) || excluded.metadados,
            atualizado_em = now()
        returning id
    """

    parametros = {
        "id_externo": f"api-football:{fixture_id}",
        "competicao_id": competicao_id,
        "rodada": league.get("round"),
        "mandante": home.get("name") or "Mandante",
        "visitante": away.get("name") or "Visitante",
        "mandante_logo_url": home.get("logo"),
        "visitante_logo_url": away.get("logo"),
        "inicio_em": inicio_em,
        "estadio": venue.get("name"),
        "cidade": venue.get("city"),
        "status": _status_interno(str(status_api.get("short") or "")),
        "gols_mandante": goals.get("home"),
        "gols_visitante": goals.get("away"),
        "metadados": json.dumps(metadados, ensure_ascii=False),
    }

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            row = cur.fetchone()
        conn.commit()

    return str(row[0]) if row else None


def _salvar_fixtures(fixtures: list[dict[str, Any]]) -> int:
    total = 0
    for item in fixtures:
        if _upsert_jogo(item):
            total += 1
    return total


def sincronizar_agenda() -> dict[str, Any]:
    team = descobrir_time_galo()
    team_id = int(team["id"])

    ultimos = _api_get(
        "/fixtures",
        {
            "team": team_id,
            "last": 30,
            "timezone": TIMEZONE,
        },
    )

    _esperar_cota()

    proximos = _api_get(
        "/fixtures",
        {
            "team": team_id,
            "next": 30,
            "timezone": TIMEZONE,
        },
    )

    salvos_ultimos = _salvar_fixtures(ultimos)
    salvos_proximos = _salvar_fixtures(proximos)

    return {
        "team_id": team_id,
        "team_name": team.get("name"),
        "team_logo": team.get("logo"),
        "ultimos": salvos_ultimos,
        "proximos": salvos_proximos,
        "cota_restante": ULTIMA_COTA_RESTANTE,
    }


def _temporadas_disponiveis(team_id: int) -> list[int]:
    dados = _api_get("/leagues", {"team": team_id})

    temporadas: set[int] = set()

    for item in dados:
        for temporada in item.get("seasons") or []:
            ano = temporada.get("year")
            if isinstance(ano, int) and ano >= 2000:
                temporadas.add(ano)

    return sorted(temporadas, reverse=True)


def sincronizar_historico_maximo() -> dict[str, Any]:
    team = descobrir_time_galo()
    team_id = int(team["id"])

    _esperar_cota()
    temporadas = _temporadas_disponiveis(team_id)

    resultados: list[dict[str, Any]] = []
    total_salvos = 0

    for temporada in temporadas:
        if ULTIMA_COTA_RESTANTE is not None and ULTIMA_COTA_RESTANTE <= 5:
            logger.warning(
                "[Jogos] interrompendo histórico: somente %s chamadas restantes hoje",
                ULTIMA_COTA_RESTANTE,
            )
            break

        _esperar_cota()

        try:
            fixtures = _api_get(
                "/fixtures",
                {
                    "team": team_id,
                    "season": temporada,
                    "timezone": TIMEZONE,
                },
            )
        except RuntimeError as exc:
            logger.warning(
                "[Jogos] temporada %s indisponível: %s",
                temporada,
                exc,
            )
            resultados.append(
                {
                    "temporada": temporada,
                    "salvos": 0,
                    "erro": str(exc),
                }
            )
            continue

        salvos = _salvar_fixtures(fixtures)
        total_salvos += salvos
        resultados.append(
            {
                "temporada": temporada,
                "salvos": salvos,
                "erro": None,
            }
        )

        logger.info(
            "[Jogos] temporada=%s encontrados=%s salvos=%s cota_restante=%s",
            temporada,
            len(fixtures),
            salvos,
            ULTIMA_COTA_RESTANTE,
        )

    return {
        "team_id": team_id,
        "team_name": team.get("name"),
        "temporadas_detectadas": temporadas,
        "temporadas_processadas": resultados,
        "total_salvos": total_salvos,
        "cota_restante": ULTIMA_COTA_RESTANTE,
    }


def _jogos_sem_eventos_gol(limite: int) -> list[dict[str, Any]]:
    sql = """
        select
            id,
            id_externo,
            mandante,
            visitante,
            inicio_em,
            metadados
        from public.jogos
        where status = 'finalizado'
          and id_externo like 'api-football:%'
          and not (coalesce(metadados, '{}'::jsonb) ? 'gols')
        order by inicio_em desc
        limit %s
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (limite,))
            colunas = [desc.name for desc in cur.description]
            return [
                dict(zip(colunas, row, strict=True))
                for row in cur.fetchall()
            ]


def _salvar_eventos_gol(jogo_id: str, eventos: list[dict[str, Any]]) -> None:
    gols: list[dict[str, Any]] = []

    for evento in eventos:
        if str(evento.get("type") or "").lower() != "goal":
            continue

        team = evento.get("team") or {}
        player = evento.get("player") or {}
        assist = evento.get("assist") or {}
        tempo = evento.get("time") or {}

        gols.append(
            {
                "team_id": team.get("id"),
                "time": team.get("name"),
                "time_logo": team.get("logo"),
                "jogador_id": player.get("id"),
                "jogador": player.get("name"),
                "assistencia_id": assist.get("id"),
                "assistencia": assist.get("name"),
                "minuto": tempo.get("elapsed"),
                "acrescimos": tempo.get("extra"),
                "detalhe": evento.get("detail"),
                "comentarios": evento.get("comments"),
            }
        )

    sql = """
        update public.jogos
        set metadados = jsonb_set(
                coalesce(metadados, '{}'::jsonb),
                '{gols}',
                %(gols)s::jsonb,
                true
            ),
            atualizado_em = now()
        where id = %(id)s
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                {
                    "id": jogo_id,
                    "gols": json.dumps(gols, ensure_ascii=False),
                },
            )
        conn.commit()


def sincronizar_autores_gols(limite: int = 12) -> dict[str, Any]:
    limite = max(1, min(int(limite), 80))
    pendentes = _jogos_sem_eventos_gol(limite)

    processados = 0
    erros: list[str] = []

    for jogo in pendentes:
        if ULTIMA_COTA_RESTANTE is not None and ULTIMA_COTA_RESTANTE <= 3:
            break

        fixture_id = str(jogo["id_externo"]).split(":")[-1]

        try:
            eventos = _api_get(
                "/fixtures/events",
                {"fixture": fixture_id},
            )
            _salvar_eventos_gol(str(jogo["id"]), eventos)
            processados += 1
        except Exception as exc:
            erros.append(f"{fixture_id}: {exc}")
            logger.exception(
                "[Jogos] falha ao buscar eventos de %s",
                fixture_id,
            )

        _esperar_cota()

    return {
        "pendentes_encontrados": len(pendentes),
        "processados": processados,
        "erros": erros,
        "cota_restante": ULTIMA_COTA_RESTANTE,
    }


def sincronizacao_inicial() -> dict[str, Any]:
    historico = sincronizar_historico_maximo()

    if ULTIMA_COTA_RESTANTE is not None and ULTIMA_COTA_RESTANTE <= 5:
        return {
            "historico": historico,
            "agenda": None,
            "gols": None,
            "aviso": "Cota diária baixa; agenda e autores dos gols ficam para a próxima execução.",
        }

    _esperar_cota()
    agenda = sincronizar_agenda()

    gols = None
    if ULTIMA_COTA_RESTANTE is None or ULTIMA_COTA_RESTANTE > 8:
        _esperar_cota()
        gols = sincronizar_autores_gols(limite=12)

    return {
        "historico": historico,
        "agenda": agenda,
        "gols": gols,
        "cota_restante": ULTIMA_COTA_RESTANTE,
    }


def _resultado_galo(
    *,
    mandante: str,
    visitante: str,
    gols_mandante: int | None,
    gols_visitante: int | None,
    status: str,
    metadados: dict[str, Any],
) -> str:
    if status == "ao_vivo":
        return "ao_vivo"

    if status != "finalizado":
        return "agendado"

    if gols_mandante is None or gols_visitante is None:
        return "finalizado"

    api = metadados.get("api_football") if isinstance(metadados, dict) else {}
    api = api if isinstance(api, dict) else {}
    team_ids = api.get("team_ids")
    team_ids = team_ids if isinstance(team_ids, dict) else {}

    team_id_config = os.getenv("API_FOOTBALL_TEAM_ID", "").strip()
    galo_casa = False

    if team_id_config and str(team_ids.get("home") or "") == team_id_config:
        galo_casa = True
    elif team_id_config and str(team_ids.get("away") or "") == team_id_config:
        galo_casa = False
    else:
        galo_casa = _eh_galo_nome(mandante)

    gols_galo = gols_mandante if galo_casa else gols_visitante
    gols_rival = gols_visitante if galo_casa else gols_mandante

    if gols_galo > gols_rival:
        return "vitoria"
    if gols_galo == gols_rival:
        return "empate"
    return "derrota"


def _serializar_jogo(row: dict[str, Any]) -> dict[str, Any]:
    metadados = row.get("metadados")
    metadados = metadados if isinstance(metadados, dict) else {}

    api = metadados.get("api_football")
    api = api if isinstance(api, dict) else {}

    team_ids = api.get("team_ids")
    team_ids = team_ids if isinstance(team_ids, dict) else {}

    team_id_config = os.getenv("API_FOOTBALL_TEAM_ID", "").strip()

    if team_id_config:
        if str(team_ids.get("home") or "") == team_id_config:
            galo_casa = True
        elif str(team_ids.get("away") or "") == team_id_config:
            galo_casa = False
        else:
            galo_casa = _eh_galo_nome(row["mandante"])
    else:
        galo_casa = _eh_galo_nome(row["mandante"])

    adversario = row["visitante"] if galo_casa else row["mandante"]
    adversario_logo = (
        row["visitante_logo_url"]
        if galo_casa
        else row["mandante_logo_url"]
    )
    galo_logo = (
        row["mandante_logo_url"]
        if galo_casa
        else row["visitante_logo_url"]
    )

    gols_galo = (
        row["gols_mandante"]
        if galo_casa
        else row["gols_visitante"]
    )
    gols_adversario = (
        row["gols_visitante"]
        if galo_casa
        else row["gols_mandante"]
    )

    resultado = _resultado_galo(
        mandante=row["mandante"],
        visitante=row["visitante"],
        gols_mandante=row["gols_mandante"],
        gols_visitante=row["gols_visitante"],
        status=row["status"],
        metadados=metadados,
    )

    gols = metadados.get("gols")
    if not isinstance(gols, list):
        gols = []

    return {
        "id": str(row["id"]),
        "id_externo": row["id_externo"],
        "inicio_em": row["inicio_em"],
        "status": row["status"],
        "status_api": api.get("status_short"),
        "resultado": resultado,
        "rodada": row["rodada"],
        "estadio": row["estadio"],
        "cidade": row["cidade"],
        "mandante": {
            "nome": row["mandante"],
            "logo_url": row["mandante_logo_url"],
            "gols": row["gols_mandante"],
        },
        "visitante": {
            "nome": row["visitante"],
            "logo_url": row["visitante_logo_url"],
            "gols": row["gols_visitante"],
        },
        "galo_casa": galo_casa,
        "galo_logo_url": galo_logo,
        "adversario": {
            "nome": adversario,
            "logo_url": adversario_logo,
            "gols": gols_adversario,
        },
        "gols_galo": gols_galo,
        "competicao": {
            "nome": row["competicao_nome"],
            "temporada": row["competicao_temporada"],
            "logo_url": row["competicao_logo_url"],
        },
        "gols": gols,
    }


def listar_jogos(
    *,
    inicio: date,
    fim: date,
) -> list[dict[str, Any]]:
    if fim < inicio:
        raise ValueError("A data final não pode ser menor que a inicial.")

    if (fim - inicio).days > 550:
        raise ValueError("Consulte no máximo 550 dias por requisição.")

    inicio_dt = datetime.combine(inicio, datetime.min.time(), tzinfo=UTC)
    fim_dt = datetime.combine(
        fim + timedelta(days=1),
        datetime.min.time(),
        tzinfo=UTC,
    )

    sql = """
        select
            j.id,
            j.id_externo,
            j.rodada,
            j.mandante,
            j.visitante,
            j.mandante_logo_url,
            j.visitante_logo_url,
            j.inicio_em,
            j.estadio,
            j.cidade,
            j.status,
            j.gols_mandante,
            j.gols_visitante,
            j.metadados,
            c.nome as competicao_nome,
            c.temporada as competicao_temporada,
            c.logo_url as competicao_logo_url
        from public.jogos j
        left join public.competicoes c on c.id = j.competicao_id
        where j.inicio_em >= %s
          and j.inicio_em < %s
        order by j.inicio_em asc
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (inicio_dt, fim_dt))
            colunas = [desc.name for desc in cur.description]
            rows = [
                dict(zip(colunas, row, strict=True))
                for row in cur.fetchall()
            ]

    return [_serializar_jogo(row) for row in rows]


def status_jogos() -> dict[str, Any]:
    sql = """
        select
            count(*) as total,
            count(*) filter (where status = 'finalizado') as finalizados,
            count(*) filter (where status = 'agendado') as agendados,
            count(*) filter (where status = 'ao_vivo') as ao_vivo,
            min(inicio_em) as primeiro_jogo,
            max(inicio_em) as ultimo_jogo,
            max(atualizado_em) as atualizado_em
        from public.jogos
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone()
            colunas = [desc.name for desc in cur.description]

    resultado = dict(zip(colunas, row, strict=True))
    resultado["api_configurada"] = bool(os.getenv("API_FOOTBALL_KEY", "").strip())
    resultado["cota_restante_ultima_execucao"] = ULTIMA_COTA_RESTANTE
    return resultado
