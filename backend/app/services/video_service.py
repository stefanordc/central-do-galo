from __future__ import annotations

import json
import logging
import re
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver

from app.core.config import get_settings
from app.db.pool import pool

logger = logging.getLogger("central_galo.youtube")
settings = get_settings()

BACKEND_DIR = Path(__file__).resolve().parents[2]
TIPOS_VALIDOS = {"video", "short", "live"}


class YoutubeScrapeError(RuntimeError):
    pass


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
        set fonte_id = excluded.fonte_id,
            titulo = excluded.titulo,
            url = excluded.url,
            thumbnail_url = coalesce(excluded.thumbnail_url, public.videos.thumbnail_url),
            descricao = coalesce(excluded.descricao, public.videos.descricao),
            tipo = case
                when public.videos.tipo = 'live' or excluded.tipo = 'live' then 'live'
                when public.videos.tipo = 'short' or excluded.tipo = 'short' then 'short'
                else 'video'
            end,
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

        profile_dir = Path(settings.youtube_scrape_profile_dir)
        if not profile_dir.is_absolute():
            profile_dir = BACKEND_DIR / profile_dir
        profile_dir.mkdir(parents=True, exist_ok=True)

        kwargs: dict[str, Any] = {
            "uc": True,
            "locale_code": "pt-BR",
            "page_load_strategy": "eager",
            "user_data_dir": str(profile_dir),
        }
        if settings.youtube_scrape_headless:
            kwargs["headless2"] = True
        else:
            kwargs["headed"] = True

        try:
            self.driver = Driver(**kwargs)
        except Exception as exc:
            logger.warning(
                "[YouTube] perfil UC persistente indisponível (%s); tentando perfil temporário",
                exc,
            )
            kwargs.pop("user_data_dir", None)
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
            const containers = Array.from(document.querySelectorAll(
              'ytd-rich-item-renderer, ytm-shorts-lockup-view-model, ytd-grid-video-renderer, yt-lockup-view-model'
            ));
            const saida = [];
            const vistos = new Set();

            function videoId(href) {
              if (!href) return null;
              try {
                const url = new URL(href, location.origin);
                if (tipo === 'short') {
                  const m = url.pathname.match(/\\/shorts\\/([A-Za-z0-9_-]{6,})/);
                  return m ? m[1] : null;
                }
                if (url.pathname === '/watch') return url.searchParams.get('v');
              } catch (_) {}
              return null;
            }

            for (const card of containers) {
              const links = Array.from(card.querySelectorAll('a[href]'));
              const link = links.find((a) => videoId(a.getAttribute('href')));
              if (!link) continue;
              const href = link.href || link.getAttribute('href') || '';
              const id = videoId(href);
              if (!id || vistos.has(id)) continue;

              const cardText = (card.innerText || '').trim();
              const lowerText = cardText.toLowerCase();
              if (lowerText.includes('só para membros') || lowerText.includes('members only')) continue;

              const titleNode = card.querySelector(
                'a.ytLockupMetadataViewModelTitle, #video-title-link, #video-title, h3 a[href]'
              );
              let title = '';
              if (titleNode) {
                title = (titleNode.getAttribute('title') || titleNode.textContent || '').trim();
              }
              if (!title) {
                title = (link.getAttribute('title') || link.getAttribute('aria-label') || '').trim();
              }
              if (!title) continue;

              const img = card.querySelector('img[src*="i.ytimg.com"]');
              const thumb = img ? (img.currentSrc || img.src || img.getAttribute('src') || '') : '';

              const badge = card.querySelector(
                'yt-thumbnail-badge-view-model .ytBadgeShapeText, ytd-thumbnail-overlay-time-status-renderer #text, badge-shape .ytBadgeShapeText'
              );
              const durationText = badge ? (badge.textContent || '').trim() : '';

              const metadataNodes = Array.from(card.querySelectorAll(
                '.ytContentMetadataViewModelMetadataText, #metadata-line span, ytd-video-meta-block #metadata-line span'
              ));
              const metadataText = metadataNodes.map((node) => (node.textContent || '').trim()).filter(Boolean).join(' • ');

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

            // Fallback para layouts em que o wrapper ainda não é conhecido.
            if (!saida.length) {
              const anchors = Array.from(document.querySelectorAll('a[href*="/watch?v="], a[href*="/shorts/"]'));
              for (const link of anchors) {
                const href = link.href || link.getAttribute('href') || '';
                const id = videoId(href);
                if (!id || vistos.has(id)) continue;
                const title = (link.getAttribute('title') || link.getAttribute('aria-label') || link.textContent || '').trim();
                if (!title) continue;
                vistos.add(id);
                saida.push({ video_id: id, href, titulo: title, thumbnail_url: '', duration_text: '', metadata_text: '', card_text: '' });
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

        # Fluxo pedido para a aba de vídeos: escolher explicitamente o filtro Público.
        # Nas outras abas, usa o mesmo filtro somente se ele existir no DOM.
        if tipo == "video":
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
    scraper = YoutubePublicScraper()

    try:
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

            for tipo, url in abas:
                if not isinstance(url, str) or not url.strip():
                    continue

                try:
                    items = scraper.coletar_aba(
                        url.strip(),
                        tipo=tipo,
                        limite=settings.youtube_items_per_section,
                        slug=fonte["slug"],
                    )
                except Exception as exc:
                    logger.exception("[YouTube] falha em %s (%s): %s", fonte["slug"], tipo, exc)
                    fonte_resultado["erros"].append(f"{tipo}: {exc}")
                    continue

                total_processados += len(items)
                for item in items:
                    salvar_video(fonte_id=fonte["id"], **item)
                    total_salvos += 1

                if tipo == "video":
                    fonte_resultado["videos"] = len(items)
                elif tipo == "short":
                    fonte_resultado["shorts"] = len(items)
                elif tipo == "live":
                    fonte_resultado["lives"] = len(items)

            resultados.append(fonte_resultado)
    finally:
        scraper.close()

    return {
        "fontes": len(fontes),
        "processados": total_processados,
        "salvos": total_salvos,
        "resultados": resultados,
    }
