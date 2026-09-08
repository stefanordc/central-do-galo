from __future__ import annotations

import atexit
import json
import logging
import os
import random
import shutil
import time
import unicodedata
from pathlib import Path
from datetime import UTC, date, datetime, timedelta
from typing import Any

import requests
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.common.by import By

from app.db.pool import pool

logger = logging.getLogger("central_galo.jogos")

SOFASCORE_BASE = "https://www.sofascore.com/api/v1"
SOFASCORE_TEAM_ID = int(os.getenv("SOFASCORE_ATLETICO_TEAM_ID", "1977"))

STATUS_FINALIZADOS = {"finished"}
STATUS_AO_VIVO = {"inprogress"}
STATUS_ADIADOS = {"postponed", "canceled", "cancelled", "suspended"}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/152.0.0.0 Safari/537.36"
)

REQUEST_INTERVAL = 0.35
MAX_RETRIES = 2
MAX_PAGINAS_HISTORICO = 120

_CLIENTE_SOFASCORE: "SofaScoreBrowserClient | None" = None



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


def _silent_uc_del(self) -> None:
    try:
        self.quit()
    except Exception:
        pass


uc.Chrome.__del__ = _silent_uc_del


def _limpar_cache_undetected_chromedriver() -> None:
    caminhos = [
        Path.home() / "AppData" / "Roaming" / "undetected_chromedriver",
        Path.home() / "appdata" / "roaming" / "undetected_chromedriver",
        Path.home() / ".local" / "share" / "undetected_chromedriver",
        Path.home() / "Library" / "Application Support" / "undetected_chromedriver",
    ]

    for caminho in caminhos:
        if not caminho.is_dir():
            continue
        try:
            shutil.rmtree(caminho)
            logger.info(
                "[Jogos] cache do undetected_chromedriver removido: %s",
                caminho,
            )
        except Exception:
            pass


def _injetar_anti_deteccao(driver: Any) -> None:
    script = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'languages', {get: () => ['pt-BR', 'pt', 'en-US', 'en']});
    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
    window.chrome = window.chrome || {runtime: {}};
    """
    try:
        driver.execute_script(script)
    except Exception:
        pass


def _criar_driver_chrome() -> Any:
    """Cria um Chrome compartilhado para atravessar a proteção do Sofascore."""

    def opcoes_uc() -> Any:
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(f"--user-agent={USER_AGENT}")
        options.add_experimental_option(
            "prefs",
            {
                "profile.default_content_setting_values.notifications": 2,
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
            },
        )
        return options

    try:
        logger.info("[Jogos] iniciando undetected_chromedriver")
        driver = uc.Chrome(options=opcoes_uc(), headless=True)
    except Exception as primeiro_erro:
        logger.warning(
            "[Jogos] falha ao iniciar undetected_chromedriver: %s",
            str(primeiro_erro).splitlines()[0],
        )
        _limpar_cache_undetected_chromedriver()

        try:
            driver = uc.Chrome(options=opcoes_uc(), headless=True)
        except Exception as segundo_erro:
            logger.warning(
                "[Jogos] segunda tentativa com undetected_chromedriver falhou: %s",
                str(segundo_erro).splitlines()[0],
            )
            logger.info("[Jogos] tentando Selenium/Chrome padrão")

            options = webdriver.ChromeOptions()
            options.add_argument("--headless=new")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument(f"--user-agent={USER_AGENT}")
            options.add_experimental_option(
                "excludeSwitches",
                ["enable-automation"],
            )
            options.add_experimental_option(
                "useAutomationExtension",
                False,
            )
            driver = webdriver.Chrome(options=options)

    driver.set_page_load_timeout(45)
    driver.implicitly_wait(5)
    _injetar_anti_deteccao(driver)
    return driver


class SofaScoreBrowserClient:
    """Cliente híbrido: requests + cookies do Chrome + fetch() + navegação."""

    def __init__(self) -> None:
        self.driver = _criar_driver_chrome()
        self.sessao: requests.Session | None = None

        logger.info("[Jogos] abrindo Sofascore para obter cookies")
        self.driver.get("https://www.sofascore.com/")
        time.sleep(2.0)
        self.renovar_sessao()

    def renovar_sessao(self) -> None:
        if self.sessao is not None:
            try:
                self.sessao.close()
            except Exception:
                pass

        sessao = requests.Session()
        sessao.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.sofascore.com/",
                "Origin": "https://www.sofascore.com",
            }
        )

        try:
            for cookie in self.driver.get_cookies():
                try:
                    sessao.cookies.set(
                        cookie["name"],
                        cookie["value"],
                        domain=cookie.get("domain"),
                    )
                except Exception:
                    pass
        except Exception:
            pass

        self.sessao = sessao

    def _fetch_via_js(self, url: str, timeout_s: int = 15) -> dict[str, Any] | None:
        js = """
        const callback = arguments[arguments.length - 1];
        fetch(arguments[0], {
            headers: {'Accept': 'application/json, text/plain, */*'},
            credentials: 'include',
            mode: 'cors'
        })
        .then(async r => {
            const text = await r.text();
            callback(JSON.stringify({ok: r.ok, status: r.status, text: text}));
        })
        .catch(e => callback(JSON.stringify({ok: false, status: 0, text: '', error: String(e)})));
        """

        try:
            self.driver.set_script_timeout(timeout_s)
            retorno = self.driver.execute_async_script(js, url)
            if not retorno:
                return None

            envelope = json.loads(retorno)
            if not envelope.get("ok"):
                logger.debug(
                    "[Jogos] fetch JS falhou status=%s url=%s",
                    envelope.get("status"),
                    url,
                )
                return None

            texto = envelope.get("text") or ""
            if not texto:
                return None

            data = json.loads(texto)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def _abrir_endpoint_no_browser(self, url: str) -> dict[str, Any] | None:
        try:
            self.driver.get(url)
            time.sleep(0.8)

            texto: str | None = None
            try:
                texto = self.driver.find_element(By.TAG_NAME, "pre").text
            except Exception:
                try:
                    texto = self.driver.execute_script(
                        "return document.body ? document.body.innerText : '';"
                    )
                except Exception:
                    texto = None

            if not texto:
                return None

            data = json.loads(texto)

            # Volta à origem para manter o contexto/cookies do site.
            self.driver.get("https://www.sofascore.com/")
            time.sleep(0.4)
            self.renovar_sessao()

            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def get_json(self, url: str, retries: int = MAX_RETRIES) -> dict[str, Any]:
        ultimo_erro: Any = None

        # 1) requests com os cookies que o Chrome já obteve.
        for tentativa in range(1, retries + 1):
            try:
                if self.sessao is None:
                    self.renovar_sessao()

                response = self.sessao.get(url, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        time.sleep(REQUEST_INTERVAL)
                        return data

                ultimo_erro = f"HTTP {response.status_code}"
                logger.debug(
                    "[Jogos] requests tentativa=%s status=%s url=%s",
                    tentativa,
                    response.status_code,
                    url,
                )
            except Exception as exc:
                ultimo_erro = exc

            time.sleep(random.uniform(0.25, 0.55))

        # 2) fetch() dentro do navegador real.
        for tentativa in range(1, retries + 1):
            data = self._fetch_via_js(url, timeout_s=15)
            if data is not None:
                logger.info("[Jogos] endpoint obtido via fetch do Chrome")
                time.sleep(REQUEST_INTERVAL)
                return data

            ultimo_erro = f"fetch JS falhou (tentativa {tentativa})"
            time.sleep(random.uniform(0.25, 0.55))

        # 3) abre o endpoint no Chrome e lê o JSON do body/pre.
        self.renovar_sessao()
        data = self._abrir_endpoint_no_browser(url)
        if data is not None:
            logger.info("[Jogos] endpoint obtido por navegação direta no Chrome")
            time.sleep(REQUEST_INTERVAL)
            return data

        raise RuntimeError(f"Falha ao buscar {url}: {ultimo_erro}")

    def fechar(self) -> None:
        if self.sessao is not None:
            try:
                self.sessao.close()
            except Exception:
                pass
            self.sessao = None

        try:
            if self.driver is not None:
                self.driver.quit()
        except Exception:
            pass
        finally:
            try:
                service = getattr(self.driver, "service", None)
                if service is not None:
                    service.process = None
            except Exception:
                pass
            self.driver = None


def _cliente_sofascore() -> SofaScoreBrowserClient:
    global _CLIENTE_SOFASCORE

    if _CLIENTE_SOFASCORE is None:
        _CLIENTE_SOFASCORE = SofaScoreBrowserClient()

    return _CLIENTE_SOFASCORE


def fechar_cliente_sofascore() -> None:
    global _CLIENTE_SOFASCORE

    if _CLIENTE_SOFASCORE is not None:
        _CLIENTE_SOFASCORE.fechar()
        _CLIENTE_SOFASCORE = None


atexit.register(fechar_cliente_sofascore)


def _sofascore_get(endpoint: str) -> dict[str, Any]:
    url = f"{SOFASCORE_BASE}{endpoint}"
    return _cliente_sofascore().get_json(url)



def _status_interno(status: dict[str, Any] | None) -> str:
    status = status or {}
    tipo = str(status.get("type") or "").lower().strip()

    if tipo in STATUS_FINALIZADOS:
        return "finalizado"
    if tipo in STATUS_AO_VIVO:
        return "ao_vivo"
    if tipo in STATUS_ADIADOS:
        return "adiado"
    return "agendado"


def _logo_time(team: dict[str, Any] | None) -> str | None:
    team = team or {}
    team_id = team.get("id")
    if team_id is None:
        return None
    return f"https://img.sofascore.com/api/v1/team/{team_id}/image"


def _logo_competicao(evento: dict[str, Any]) -> str | None:
    tournament = evento.get("tournament") or {}
    unique_tournament = tournament.get("uniqueTournament") or {}

    unique_id = unique_tournament.get("id")
    if unique_id is not None:
        return (
            "https://img.sofascore.com/api/v1/"
            f"unique-tournament/{unique_id}/image"
        )

    tournament_id = tournament.get("id")
    if tournament_id is not None:
        return (
            "https://img.sofascore.com/api/v1/"
            f"tournament/{tournament_id}/image"
        )

    return None


def _nome_competicao(evento: dict[str, Any]) -> str:
    tournament = evento.get("tournament") or {}
    unique_tournament = tournament.get("uniqueTournament") or {}

    return (
        str(unique_tournament.get("name") or "").strip()
        or str(tournament.get("name") or "").strip()
        or "Competição"
    )


def _temporada_evento(evento: dict[str, Any]) -> str | None:
    season = evento.get("season") or {}

    nome = season.get("name")
    if nome is not None and str(nome).strip():
        return str(nome).strip()

    year = season.get("year")
    if year is not None:
        return str(year)

    timestamp = evento.get("startTimestamp")
    if isinstance(timestamp, (int, float)):
        return str(datetime.fromtimestamp(timestamp, tz=UTC).year)

    return None


def _upsert_competicao(evento: dict[str, Any]) -> str | None:
    tournament = evento.get("tournament") or {}
    unique_tournament = tournament.get("uniqueTournament") or {}
    category = tournament.get("category") or {}

    nome = _nome_competicao(evento)
    temporada = _temporada_evento(evento)

    external_id = unique_tournament.get("id") or tournament.get("id")

    pais = category.get("name") if isinstance(category, dict) else None

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
        "id_externo": (
            f"sofascore:{external_id}"
            if external_id is not None
            else None
        ),
        "nome": nome,
        "temporada": temporada,
        "pais": pais,
        "logo_url": _logo_competicao(evento),
    }

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            row = cur.fetchone()
        conn.commit()

    return str(row[0]) if row else None


def _placar_atual(score: dict[str, Any] | None) -> int | None:
    score = score or {}

    for chave in ("current", "normaltime", "display"):
        valor = score.get(chave)

        if isinstance(valor, int):
            return valor
        if isinstance(valor, float):
            return int(valor)
        if isinstance(valor, str) and valor.isdigit():
            return int(valor)

    return None


def _inicio_evento(evento: dict[str, Any]) -> datetime | None:
    timestamp = evento.get("startTimestamp")

    if not isinstance(timestamp, (int, float)):
        return None

    return datetime.fromtimestamp(timestamp, tz=UTC)


def _round_text(evento: dict[str, Any]) -> str | None:
    round_info = evento.get("roundInfo") or {}

    if isinstance(round_info, dict):
        name = round_info.get("name")
        if name:
            return str(name)

        round_number = round_info.get("round")
        if round_number is not None:
            return f"Rodada {round_number}"

    return None


def _venue_info(evento: dict[str, Any]) -> tuple[str | None, str | None]:
    venue = evento.get("venue") or {}

    if not isinstance(venue, dict):
        return None, None

    estadio = None
    stadium = venue.get("stadium")
    if isinstance(stadium, dict):
        estadio = stadium.get("name")

    if not estadio:
        estadio = venue.get("name")

    cidade = None
    city = venue.get("city")
    if isinstance(city, dict):
        cidade = city.get("name")
    else:
        cidade = city

    return (
        str(estadio).strip() if estadio else None,
        str(cidade).strip() if cidade else None,
    )


def _metadados_evento(evento: dict[str, Any]) -> dict[str, Any]:
    tournament = evento.get("tournament") or {}
    unique_tournament = tournament.get("uniqueTournament") or {}
    home = evento.get("homeTeam") or {}
    away = evento.get("awayTeam") or {}
    status = evento.get("status") or {}

    return {
        "fonte": "sofascore",
        "sofascore": {
            "event_id": evento.get("id"),
            "slug": evento.get("slug"),
            "status_type": status.get("type"),
            "status_description": status.get("description"),
            "tournament_id": tournament.get("id"),
            "unique_tournament_id": unique_tournament.get("id"),
            "season_id": (evento.get("season") or {}).get("id"),
            "team_ids": {
                "home": home.get("id"),
                "away": away.get("id"),
            },
        },
    }


def _upsert_jogo(evento: dict[str, Any]) -> str | None:
    event_id = evento.get("id")
    inicio = _inicio_evento(evento)

    if event_id is None or inicio is None:
        return None

    home = evento.get("homeTeam") or {}
    away = evento.get("awayTeam") or {}
    home_score = evento.get("homeScore") or {}
    away_score = evento.get("awayScore") or {}

    competicao_id = _upsert_competicao(evento)
    estadio, cidade = _venue_info(evento)

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
            estadio = coalesce(excluded.estadio, public.jogos.estadio),
            cidade = coalesce(excluded.cidade, public.jogos.cidade),
            status = excluded.status,
            gols_mandante = excluded.gols_mandante,
            gols_visitante = excluded.gols_visitante,
            metadados = coalesce(public.jogos.metadados, '{}'::jsonb)
                        || excluded.metadados,
            atualizado_em = now()
        returning id
    """

    parametros = {
        "id_externo": f"sofascore:{event_id}",
        "competicao_id": competicao_id,
        "rodada": _round_text(evento),
        "mandante": str(home.get("name") or "Mandante"),
        "visitante": str(away.get("name") or "Visitante"),
        "mandante_logo_url": _logo_time(home),
        "visitante_logo_url": _logo_time(away),
        "inicio_em": inicio,
        "estadio": estadio,
        "cidade": cidade,
        "status": _status_interno(evento.get("status")),
        "gols_mandante": _placar_atual(home_score),
        "gols_visitante": _placar_atual(away_score),
        "metadados": json.dumps(
            _metadados_evento(evento),
            ensure_ascii=False,
        ),
    }

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, parametros)
            row = cur.fetchone()
        conn.commit()

    return str(row[0]) if row else None


def _salvar_eventos(eventos: list[dict[str, Any]]) -> int:
    total = 0

    for evento in eventos:
        if _upsert_jogo(evento):
            total += 1

    return total


def _buscar_pagina_time(direcao: str, pagina: int) -> dict[str, Any]:
    if direcao not in {"last", "next"}:
        raise ValueError("Direção inválida.")

    return _sofascore_get(
        f"/team/{SOFASCORE_TEAM_ID}/events/{direcao}/{pagina}"
    )


def sincronizar_agenda() -> dict[str, Any]:
    eventos: list[dict[str, Any]] = []

    dados_passados = _buscar_pagina_time("last", 0)
    eventos.extend(dados_passados.get("events") or [])

    pagina = 0
    paginas_futuras = 0

    while pagina < 10:
        dados = _buscar_pagina_time("next", pagina)
        pagina_eventos = dados.get("events") or []

        if not isinstance(pagina_eventos, list):
            pagina_eventos = []

        eventos.extend(pagina_eventos)
        paginas_futuras += 1

        if not dados.get("hasNextPage"):
            break

        pagina += 1

    unicos: dict[int, dict[str, Any]] = {}

    for evento in eventos:
        event_id = evento.get("id")
        if isinstance(event_id, int):
            unicos[event_id] = evento

    salvos = _salvar_eventos(list(unicos.values()))

    agora = datetime.now(UTC)
    passados = 0
    futuros = 0

    for evento in unicos.values():
        inicio = _inicio_evento(evento)
        if inicio is None:
            continue
        if inicio <= agora:
            passados += 1
        else:
            futuros += 1

    return {
        "fonte": "sofascore",
        "team_id": SOFASCORE_TEAM_ID,
        "encontrados": len(unicos),
        "passados": passados,
        "futuros": futuros,
        "salvos": salvos,
        "paginas_futuras": paginas_futuras,
    }


def sincronizar_historico_maximo() -> dict[str, Any]:
    pagina = 0
    total_salvos = 0
    total_encontrados = 0
    primeiro_jogo: datetime | None = None
    ultimo_jogo: datetime | None = None
    paginas_processadas = 0

    limite_data = datetime(2000, 1, 1, tzinfo=UTC)

    while pagina < MAX_PAGINAS_HISTORICO:
        dados = _buscar_pagina_time("last", pagina)
        eventos = dados.get("events") or []

        if not isinstance(eventos, list) or not eventos:
            break

        paginas_processadas += 1
        total_encontrados += len(eventos)
        total_salvos += _salvar_eventos(eventos)

        datas = [
            data_evento
            for evento in eventos
            if (data_evento := _inicio_evento(evento)) is not None
        ]

        if datas:
            menor = min(datas)
            maior = max(datas)

            primeiro_jogo = (
                menor
                if primeiro_jogo is None
                else min(primeiro_jogo, menor)
            )

            ultimo_jogo = (
                maior
                if ultimo_jogo is None
                else max(ultimo_jogo, maior)
            )

            logger.info(
                "[Jogos] Sofascore histórico página=%s "
                "eventos=%s período=%s até %s",
                pagina,
                len(eventos),
                menor.date(),
                maior.date(),
            )

            if menor <= limite_data:
                break

        if not dados.get("hasNextPage"):
            break

        pagina += 1

    return {
        "fonte": "sofascore",
        "team_id": SOFASCORE_TEAM_ID,
        "paginas_processadas": paginas_processadas,
        "total_encontrados": total_encontrados,
        "total_salvos": total_salvos,
        "primeiro_jogo": primeiro_jogo,
        "ultimo_jogo": ultimo_jogo,
    }


def _jogos_sem_eventos_gol(limite: int) -> list[dict[str, Any]]:
    sql = """
        select
            id,
            id_externo,
            mandante,
            visitante,
            mandante_logo_url,
            visitante_logo_url,
            inicio_em,
            metadados
        from public.jogos
        where status = 'finalizado'
          and id_externo like 'sofascore:%%'
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


def _evento_id_jogo(jogo: dict[str, Any]) -> str | None:
    id_externo = str(jogo.get("id_externo") or "")

    if ":" not in id_externo:
        return None

    return id_externo.split(":", 1)[1].strip() or None


def _salvar_eventos_gol(
    jogo: dict[str, Any],
    incidents: list[dict[str, Any]],
) -> None:
    gols: list[dict[str, Any]] = []

    for incident in incidents:
        if str(incident.get("incidentType") or "").lower() != "goal":
            continue

        player = incident.get("player") or {}
        assist = incident.get("assist1") or incident.get("assist") or {}

        is_home = incident.get("isHome")

        if is_home is True:
            nome_time = jogo.get("mandante")
            logo_time = jogo.get("mandante_logo_url")
        elif is_home is False:
            nome_time = jogo.get("visitante")
            logo_time = jogo.get("visitante_logo_url")
        else:
            team = incident.get("team") or {}
            nome_time = team.get("name")
            logo_time = _logo_time(team)

        gols.append(
            {
                "time": nome_time,
                "time_logo": logo_time,
                "jogador_id": player.get("id"),
                "jogador": player.get("name"),
                "assistencia_id": (
                    assist.get("id")
                    if isinstance(assist, dict)
                    else None
                ),
                "assistencia": (
                    assist.get("name")
                    if isinstance(assist, dict)
                    else None
                ),
                "minuto": incident.get("time"),
                "acrescimos": incident.get("addedTime"),
                "detalhe": incident.get("incidentClass"),
                "home_score": incident.get("homeScore"),
                "away_score": incident.get("awayScore"),
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
                    "id": jogo["id"],
                    "gols": json.dumps(
                        gols,
                        ensure_ascii=False,
                    ),
                },
            )
        conn.commit()


def sincronizar_autores_gols(limite: int = 12) -> dict[str, Any]:
    limite = max(1, min(int(limite), 80))
    pendentes = _jogos_sem_eventos_gol(limite)

    processados = 0
    erros: list[str] = []

    for jogo in pendentes:
        event_id = _evento_id_jogo(jogo)

        if not event_id:
            continue

        try:
            payload = _sofascore_get(f"/event/{event_id}/incidents")
            incidents = payload.get("incidents") or []

            if not isinstance(incidents, list):
                incidents = []

            _salvar_eventos_gol(jogo, incidents)
            processados += 1

        except Exception as exc:
            erros.append(f"{event_id}: {exc}")
            logger.exception(
                "[Jogos] falha ao buscar gols do evento %s",
                event_id,
            )

    return {
        "fonte": "sofascore",
        "pendentes_encontrados": len(pendentes),
        "processados": processados,
        "erros": erros,
    }


def sincronizacao_inicial() -> dict[str, Any]:
    historico: dict[str, Any] | None = None
    agenda: dict[str, Any] | None = None
    gols: dict[str, Any] | None = None
    erros: list[str] = []

    try:
        historico = sincronizar_historico_maximo()
    except Exception as exc:
        logger.exception(
            "[Jogos] falha na importação histórica do Sofascore"
        )
        erros.append(f"historico: {exc}")

    try:
        agenda = sincronizar_agenda()
    except Exception as exc:
        logger.exception(
            "[Jogos] falha na sincronização da agenda do Sofascore"
        )
        erros.append(f"agenda: {exc}")

    try:
        gols = sincronizar_autores_gols(limite=12)
    except Exception as exc:
        logger.exception(
            "[Jogos] falha ao sincronizar autores dos gols"
        )
        erros.append(f"gols: {exc}")

    return {
        "fonte": "sofascore",
        "historico": historico,
        "agenda": agenda,
        "gols": gols,
        "erros": erros,
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

    sofa = (
        metadados.get("sofascore")
        if isinstance(metadados, dict)
        else {}
    )
    sofa = sofa if isinstance(sofa, dict) else {}

    team_ids = sofa.get("team_ids")
    team_ids = team_ids if isinstance(team_ids, dict) else {}

    if str(team_ids.get("home") or "") == str(SOFASCORE_TEAM_ID):
        galo_casa = True
    elif str(team_ids.get("away") or "") == str(SOFASCORE_TEAM_ID):
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

    sofa = metadados.get("sofascore")
    sofa = sofa if isinstance(sofa, dict) else {}

    team_ids = sofa.get("team_ids")
    team_ids = team_ids if isinstance(team_ids, dict) else {}

    if str(team_ids.get("home") or "") == str(SOFASCORE_TEAM_ID):
        galo_casa = True
    elif str(team_ids.get("away") or "") == str(SOFASCORE_TEAM_ID):
        galo_casa = False
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

    gols_galo = row["gols_mandante"] if galo_casa else row["gols_visitante"]
    gols_adversario = (
        row["gols_visitante"] if galo_casa else row["gols_mandante"]
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
        "status_api": sofa.get("status_type"),
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

    inicio_dt = datetime.combine(
        inicio,
        datetime.min.time(),
        tzinfo=UTC,
    )
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
        left join public.competicoes c
            on c.id = j.competicao_id
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
    resultado["fonte"] = "sofascore"
    resultado["api_configurada"] = True
    resultado["team_id"] = SOFASCORE_TEAM_ID
    return resultado
