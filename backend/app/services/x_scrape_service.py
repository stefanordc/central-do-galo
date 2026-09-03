from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup, Tag
from psycopg.types.json import Jsonb
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import Driver


from app.core.config import get_settings
from app.db.pool import pool

settings = get_settings()
logger = logging.getLogger("central_galo.x_scrape")
logger.setLevel(logging.INFO)

X_OEMBED_URL = "https://publish.x.com/oembed"
X_BASE_URL = "https://x.com"
TWITTER_SNOWFLAKE_EPOCH_MS = 1288834974657
BACKEND_DIR = Path(__file__).resolve().parents[2]


class XScrapeError(RuntimeError):
    pass


class XScrapeBlockedError(XScrapeError):
    pass


@dataclass
class ContaScrape:
    id: str
    nome: str
    usuario: str
    foto_url: str | None
    ultimo_post_id: str | None


@dataclass
class ScrapedPost:
    post_id: str
    url: str
    texto: str | None
    publicado_em: datetime | None
    metricas: dict[str, int]
    midia: list[dict[str, Any]]
    autor_nome: str | None = None
    autor_usuario: str | None = None
    autor_foto_url: str | None = None
    autor_verificado: bool = False


class XScrapeService:
    """Coleta pública do X com SeleniumBase UC + oEmbed oficial.

    Não exige login. O navegador roda oculto (headless2) e usa os seletores
    estáveis observados no DOM atual do X: ``article[data-testid="tweet"]``
    e ``a[href*="/status/"]``. Não há resolução automática de CAPTCHA.
    """

    def __init__(self) -> None:
        configured_ua = (settings.x_scrape_user_agent or "").strip()
        if not configured_ua.lower().startswith("mozilla/"):
            configured_ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            )
        self.user_agent = configured_ua
        self.driver: Any | None = None
        self.oembed_client = httpx.Client(
            timeout=settings.x_sync_timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": configured_ua,
                "Accept": "application/json",
            },
        )

    def _driver(self):
        if self.driver is not None:
            return self.driver

        logger.info(
            "[scrape] iniciando SeleniumBase UC | headless2=%s",
            settings.x_scrape_headless,
        )

        profile_name = (settings.x_scrape_profile_dir or ".x_public_uc_profile").strip()
        # Perfis .x_chrome_profile das versões antigas podiam ter sido abertos
        # por Chrome/Selenium comum para login manual. SeleniumBase recomenda
        # que user_data_dir usado em UC seja criado pelo próprio UC.
        if profile_name in {".x_chrome_profile", "x_chrome_profile"}:
            profile_name = ".x_public_uc_profile"
        profile_dir = Path(profile_name)
        if not profile_dir.is_absolute():
            profile_dir = BACKEND_DIR / profile_dir
        profile_dir.mkdir(parents=True, exist_ok=True)

        kwargs = {
            "uc": True,
            "locale_code": "pt-BR",
            "page_load_strategy": "eager",
            "user_data_dir": str(profile_dir),
        }
        if settings.x_scrape_headless:
            kwargs["headless2"] = True
        else:
            kwargs["headed"] = True

        try:
            self.driver = Driver(**kwargs)
        except Exception as exc:
            # Um segundo processo (ex.: backend + diagnosticar_x.py) pode manter
            # o perfil persistente bloqueado. Nessa situação, cai para um
            # perfil temporário UC sem alterar a estratégia de scraping.
            logger.warning(
                "[scrape] perfil UC persistente indisponível (%s); "
                "tentando perfil temporário",
                exc,
            )
            kwargs.pop("user_data_dir", None)
            try:
                self.driver = Driver(**kwargs)
            except Exception as fallback_exc:
                raise XScrapeError(
                    "Falha ao iniciar SeleniumBase UC para o Radar do X: "
                    f"{fallback_exc}"
                ) from fallback_exc

        self.driver.set_page_load_timeout(settings.x_scrape_page_timeout_seconds)
        self.driver.set_window_size(1365, 1800)
        return self.driver

    def close(self) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                logger.exception("[scrape] erro ao encerrar Chrome")
            self.driver = None
        self.oembed_client.close()

    @staticmethod
    def sanitizar_oembed_html(html: str | None) -> str | None:
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            script.decompose()
        return str(soup).strip() or None

    @staticmethod
    def texto_do_oembed_html(html: str | None) -> str | None:
        """Extrai o texto visível do tweet do HTML oficial do oEmbed.

        Serve como fallback quando o X entrega os links /status/ no DOM vivo,
        mas remove/virtualiza o container ``tweetText`` usado pelo Selenium.
        """
        if not html:
            return None
        soup = BeautifulSoup(html, "html.parser")
        blockquote = soup.find("blockquote", class_="twitter-tweet")
        if blockquote is None:
            return None
        paragrafo = blockquote.find("p")
        if paragrafo is None:
            return None
        texto = paragrafo.get_text(" ", strip=True)
        return re.sub(r"\s+", " ", texto).strip() or None

    @staticmethod
    def _parse_compact_number(texto: str | None) -> int:
        if not texto:
            return 0
        valor = texto.strip().lower().replace(" ", " ")
        match = re.search(
            r"(\d+(?:[\.,]\d+)?)\s*(k|m|mil|mi|milhão|milhões)?",
            valor,
        )
        if not match:
            return 0
        numero = float(match.group(1).replace(",", "."))
        sufixo = (match.group(2) or "").lower()
        if sufixo in {"k", "mil"}:
            numero *= 1_000
        elif sufixo in {"m", "mi", "milhão", "milhões"}:
            numero *= 1_000_000
        return int(numero)

    @classmethod
    def _metric_from_article(cls, article: Tag, testid: str) -> int:
        node = article.select_one(f'[data-testid="{testid}"]')
        if node is None:
            return 0
        candidatos = [node.get("aria-label"), node.get_text(" ", strip=True)]
        for candidato in candidatos:
            numero = cls._parse_compact_number(candidato)
            if numero:
                return numero
        return 0

    @staticmethod
    def _canonical_post_url(href: str | None, usuario: str) -> tuple[str, str] | None:
        if not href:
            return None
        absoluto = urljoin(X_BASE_URL, unescape(href))
        parsed = urlsplit(absoluto)
        if parsed.netloc.lower() not in {
            "x.com",
            "www.x.com",
            "twitter.com",
            "www.twitter.com",
        }:
            return None
        match = re.match(r"^/([^/]+)/status/(\d+)", parsed.path, flags=re.IGNORECASE)
        if not match:
            return None
        autor, post_id = match.groups()
        if autor.lower() != usuario.lower():
            return None
        return f"https://x.com/{autor}/status/{post_id}", post_id

    @classmethod
    def extrair_posts_html(
        cls,
        html: str,
        usuario: str,
        limite: int = 3,
    ) -> list[ScrapedPost]:
        """Extrai publicações próprias do DOM renderizado do x.com.

        Usa atributos semânticos do X (``data-testid``, ``role`` e links
        ``/<usuario>/status/<id>``), evitando classes CSS geradas.
        """
        soup = BeautifulSoup(html or "", "html.parser")
        resultado: list[ScrapedPost] = []
        vistos: set[str] = set()

        # O DOM atual usa article[data-testid="tweet"]. O fallback por
        # role=article mantém compatibilidade caso o testid seja removido,
        # sem depender das classes CSS efêmeras do React.
        articles = soup.select('article[data-testid="tweet"], article[role="article"]')

        for article in articles:
            contexto = article.select_one('[data-testid="socialContext"]')
            contexto_texto = contexto.get_text(" ", strip=True).lower() if contexto else ""
            if any(termo in contexto_texto for termo in ("pinned", "fixado")):
                continue

            texto_completo = article.get_text(" ", strip=True).lower()
            # Replies continuam sendo posts do próprio autor e, por isso, o
            # filtro apenas pelo href não basta. O X exibe esse contexto no
            # artigo com frases semânticas localizadas.
            if any(
                termo in texto_completo
                for termo in (
                    "replying to",
                    "in reply to",
                    "em resposta a",
                    "respondendo a",
                )
            ):
                continue

            time_tag = article.find("time")
            href = None
            if isinstance(time_tag, Tag):
                parent = time_tag.find_parent("a", href=True)
                if isinstance(parent, Tag):
                    href = parent.get("href")

            if not href:
                # Prefere links que apontem explicitamente para o perfil alvo.
                alvo = usuario.lower()
                for anchor in article.find_all("a", href=True):
                    candidate = str(anchor.get("href") or "")
                    match = re.match(
                        r"^/([^/]+)/status/(\d+)",
                        candidate,
                        flags=re.IGNORECASE,
                    )
                    if match and match.group(1).lower() == alvo:
                        href = candidate
                        break

            canonical = cls._canonical_post_url(href, usuario)
            if not canonical:
                # Reposts de terceiros caem aqui porque o autor do href não
                # corresponde ao perfil monitorado.
                continue
            url, post_id = canonical
            if post_id in vistos:
                continue
            vistos.add(post_id)

            texto_tag = article.select_one('[data-testid="tweetText"]')
            texto = texto_tag.get_text(" ", strip=True) if texto_tag else None

            publicado_em = None
            if isinstance(time_tag, Tag) and time_tag.get("datetime"):
                try:
                    publicado_em = datetime.fromisoformat(
                        str(time_tag.get("datetime")).replace("Z", "+00:00")
                    )
                except ValueError:
                    publicado_em = None
            if publicado_em is None:
                publicado_em = cls._datetime_from_snowflake(post_id)

            resultado.append(
                ScrapedPost(
                    post_id=post_id,
                    url=url,
                    texto=texto,
                    publicado_em=publicado_em,
                    metricas={
                        "reply_count": cls._metric_from_article(article, "reply"),
                        "retweet_count": cls._metric_from_article(article, "retweet"),
                        "like_count": cls._metric_from_article(article, "like"),
                    },
                    midia=[
                        {"type": "photo", "url": str(img.get("src"))}
                        for img in article.select('[data-testid="tweetPhoto"] img')
                        if img.get("src")
                    ],
                )
            )

        resultado.sort(
            key=lambda item: (
                item.publicado_em or datetime.min.replace(tzinfo=timezone.utc),
                int(item.post_id) if item.post_id.isdigit() else 0,
            ),
            reverse=True,
        )
        return resultado[:limite]

    @staticmethod
    def _parse_created_at(value: Any) -> datetime | None:
        if not value:
            return None
        texto = str(value).strip()
        try:
            dt = datetime.fromisoformat(texto.replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
        try:
            dt = parsedate_to_datetime(texto)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _midia_do_tweet(tweet: dict[str, Any]) -> list[dict[str, Any]]:
        resultado: list[dict[str, Any]] = []
        vistos: set[str] = set()

        candidatos: list[Any] = []
        entidades = tweet.get("entities")
        if isinstance(entidades, dict):
            candidatos.extend(entidades.get("media") or [])
        extended = tweet.get("extended_entities")
        if isinstance(extended, dict):
            candidatos.extend(extended.get("media") or [])
        candidatos.extend(tweet.get("mediaDetails") or [])

        for item in candidatos:
            if not isinstance(item, dict):
                continue
            url = (
                item.get("media_url_https")
                or item.get("media_url")
                or item.get("expanded_url")
            )
            if not url or str(url) in vistos:
                continue
            vistos.add(str(url))
            tipo = item.get("type") or "photo"
            resultado.append({"type": str(tipo), "url": str(url)})
        return resultado

    @classmethod
    def extrair_posts_syndication_html(
        cls,
        html: str,
        usuario: str,
        limite: int = 3,
    ) -> list[ScrapedPost]:
        """Extrai os posts do JSON __NEXT_DATA__ da timeline de syndication."""
        soup = BeautifulSoup(html or "", "html.parser")
        script = soup.find("script", id="__NEXT_DATA__")
        if not isinstance(script, Tag):
            raise XScrapeError(
                "A resposta de syndication não contém __NEXT_DATA__. "
                "O endpoint pode ter mudado ou bloqueado a requisição."
            )

        raw = script.string or script.get_text() or ""
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise XScrapeError("__NEXT_DATA__ retornou JSON inválido.") from exc

        page_props = ((payload.get("props") or {}).get("pageProps") or {})
        timeline = page_props.get("timeline") or {}
        entries = timeline.get("entries") or []
        if not isinstance(entries, list):
            raise XScrapeError("Timeline de syndication retornou estrutura inesperada.")

        resultado: list[ScrapedPost] = []
        vistos: set[str] = set()
        alvo = usuario.lower()

        for entry in entries:
            if not isinstance(entry, dict) or entry.get("type") != "tweet":
                continue
            content = entry.get("content") or {}
            tweet = content.get("tweet") if isinstance(content, dict) else None
            if not isinstance(tweet, dict):
                continue

            user = tweet.get("user") or {}
            if not isinstance(user, dict):
                user = {}
            screen_name = str(user.get("screen_name") or "").strip()
            if not screen_name or screen_name.lower() != alvo:
                # Ignora tweets de terceiros que apareçam na timeline.
                continue

            post_id = str(tweet.get("id_str") or tweet.get("id") or "").strip()
            if not post_id.isdigit() or post_id in vistos:
                continue
            vistos.add(post_id)

            resultado.append(
                ScrapedPost(
                    post_id=post_id,
                    url=f"https://x.com/{screen_name}/status/{post_id}",
                    texto=(tweet.get("full_text") or tweet.get("text") or None),
                    publicado_em=cls._parse_created_at(tweet.get("created_at")),
                    metricas={
                        "reply_count": int(tweet.get("reply_count") or 0),
                        "retweet_count": int(tweet.get("retweet_count") or 0),
                        "like_count": int(tweet.get("favorite_count") or 0),
                        "quote_count": int(tweet.get("quote_count") or 0),
                    },
                    midia=cls._midia_do_tweet(tweet),
                    autor_nome=str(user.get("name") or "").strip() or None,
                    autor_usuario=screen_name,
                    autor_foto_url=str(user.get("profile_image_url_https") or "").strip() or None,
                    autor_verificado=bool(
                        user.get("verified")
                        or user.get("is_blue_verified")
                        or user.get("verified_type")
                    ),
                )
            )

        resultado.sort(
            key=lambda item: item.publicado_em or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return resultado[:limite]

    @staticmethod
    def _datetime_from_snowflake(post_id: str) -> datetime | None:
        if not post_id.isdigit():
            return None
        try:
            timestamp_ms = (int(post_id) >> 22) + TWITTER_SNOWFLAKE_EPOCH_MS
            return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    @classmethod
    def extrair_posts_mirror_html(
        cls,
        html: str,
        usuario: str,
        limite: int = 3,
    ) -> list[ScrapedPost]:
        """Extrai URLs /usuario/status/id de um espelho público.

        O HTML do X fornecido pelo projeto confirma que o identificador está no
        href /<usuario>/status/<snowflake>. Espelhos públicos reproduzem o mesmo
        padrão nos links de detalhe. Duplicatas (hora + View Details) são
        descartadas.
        """
        soup = BeautifulSoup(html or "", "html.parser")
        alvo = usuario.lower()
        vistos: set[str] = set()
        posts: list[ScrapedPost] = []

        for anchor in soup.find_all("a", href=True):
            href = unescape(str(anchor.get("href") or "")).strip()
            if not href:
                continue
            parsed = urlsplit(urljoin("https://x.com/", href))
            match = re.match(r"^/([^/]+)/status/(\d+)", parsed.path, flags=re.IGNORECASE)
            if not match:
                continue
            autor, post_id = match.groups()
            if autor.lower() != alvo or post_id in vistos:
                continue
            vistos.add(post_id)

            posts.append(
                ScrapedPost(
                    post_id=post_id,
                    url=f"https://x.com/{usuario}/status/{post_id}",
                    texto=None,
                    publicado_em=cls._datetime_from_snowflake(post_id),
                    metricas={},
                    midia=[],
                    autor_nome=None,
                    autor_usuario=usuario,
                    autor_foto_url=None,
                    autor_verificado=False,
                )
            )

        posts.sort(
            key=lambda item: (
                item.publicado_em or datetime.min.replace(tzinfo=timezone.utc),
                int(item.post_id) if item.post_id.isdigit() else 0,
            ),
            reverse=True,
        )
        return posts[:limite]

    @staticmethod
    def _detectar_bloqueio(
        html: str,
        body_text: str = "",
        current_url: str = "",
    ) -> str | None:
        texto = f"{html}\n{body_text}".lower()
        url = (current_url or "").lower()

        if "/i/flow/login" in url:
            return "X redirecionou para fluxo de login"

        sinais = (
            ("verify you are human", "verificação humana/challenge detectado"),
            ("captcha", "CAPTCHA/challenge detectado"),
            ("cf-chl", "challenge anti-bot detectado"),
            ("rate limit exceeded", "rate limit público do X detectado"),
            ("too many requests", "rate limit público do X detectado"),
            ("something went wrong", "X retornou 'Something went wrong'"),
            ("javascript is not available", "X informou que JavaScript não está disponível"),
            ("this browser is no longer supported", "X recusou o navegador atual"),
            ("não perca o que está acontecendo", "X exibiu login-wall para acesso anônimo"),
            ("don't miss what's happening", "X exibiu login-wall para acesso anônimo"),
            ("ver mais no x", "X exibiu CTA/login-wall em vez da timeline"),
            ("see more on x", "X exibiu CTA/login-wall em vez da timeline"),
            ("log in to x", "X exige login para visualizar o perfil"),
            ("sign in to x", "X exige login para visualizar o perfil"),
        )
        for termo, motivo in sinais:
            if termo in texto:
                return motivo
        return None

    @staticmethod
    def _body_text(driver: Any) -> str:
        try:
            return (driver.find_element(By.TAG_NAME, "body").text or "").strip()
        except Exception:
            return ""

    @staticmethod
    def _outer_html(driver: Any) -> str:
        """Retorna o DOM vivo atual, não apenas o snapshot inicial do WebDriver."""
        try:
            html = driver.execute_script(
                "return document.documentElement ? document.documentElement.outerHTML : '';"
            )
            if html:
                return str(html)
        except Exception:
            pass
        try:
            return driver.page_source or ""
        except Exception:
            return ""

    @staticmethod
    def _status_links_dom(driver: Any, usuario: str) -> int:
        """Conta links canônicos do próprio perfil no DOM vivo.

        O log real mostrou texto de tweets no body mesmo com zero ``article``.
        Portanto, a presença de ``/<usuario>/status/<id>`` passa a ser o sinal
        primário de que a timeline está renderizada.
        """
        script = r"""
            const alvo = String(arguments[0] || '').toLowerCase();
            const re = /^\/([^/]+)\/status\/(\d+)/i;
            const vistos = new Set();
            for (const a of document.querySelectorAll('a[href*="/status/"]')) {
                let path = '';
                try { path = new URL(a.getAttribute('href') || '', location.origin).pathname; }
                catch (_) { continue; }
                const m = path.match(re);
                if (m && m[1].toLowerCase() === alvo) vistos.add(m[2]);
            }
            return vistos.size;
        """
        try:
            return int(driver.execute_script(script, usuario) or 0)
        except Exception:
            return 0

    @classmethod
    def _normalizar_posts_dom_vivo(
        cls,
        rows: Any,
        usuario: str,
        limite: int,
    ) -> list[ScrapedPost]:
        if not isinstance(rows, list):
            return []

        resultado: list[ScrapedPost] = []
        vistos: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue

            canonical = cls._canonical_post_url(str(row.get("href") or ""), usuario)
            if not canonical:
                continue
            url, post_id = canonical
            if post_id in vistos:
                continue

            contexto = str(row.get("social_context") or "").strip().lower()
            root_text = str(row.get("root_text") or "").strip().lower()
            if any(termo in contexto for termo in ("pinned", "fixado")):
                continue
            if any(
                termo in root_text
                for termo in (
                    "replying to",
                    "in reply to",
                    "em resposta a",
                    "respondendo a",
                )
            ):
                continue

            vistos.add(post_id)
            publicado_em = cls._parse_created_at(row.get("datetime"))
            if publicado_em is None:
                publicado_em = cls._datetime_from_snowflake(post_id)

            metricas_raw = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
            metricas = {
                "reply_count": cls._parse_compact_number(str(metricas_raw.get("reply") or "")),
                "retweet_count": cls._parse_compact_number(str(metricas_raw.get("retweet") or "")),
                "like_count": cls._parse_compact_number(str(metricas_raw.get("like") or "")),
            }

            fotos: list[dict[str, Any]] = []
            vistos_midia: set[str] = set()
            media_rows = row.get("media") or []
            if isinstance(media_rows, list):
                for item in media_rows:
                    if isinstance(item, dict):
                        src = str(item.get("url") or "").strip()
                        tipo = str(item.get("type") or "photo").strip() or "photo"
                    else:
                        src = str(item or "").strip()
                        tipo = "photo"
                    if not src or src in vistos_midia:
                        continue
                    vistos_midia.add(src)
                    fotos.append({"type": tipo, "url": src})

            # Compatibilidade com dumps/debug de versões anteriores.
            for src in row.get("photos") or []:
                src = str(src or "").strip()
                if src and src not in vistos_midia:
                    vistos_midia.add(src)
                    fotos.append({"type": "photo", "url": src})

            resultado.append(
                ScrapedPost(
                    post_id=post_id,
                    url=url,
                    texto=str(row.get("text") or "").strip() or None,
                    publicado_em=publicado_em,
                    metricas=metricas,
                    midia=fotos,
                )
            )

        return cls._ordenar_posts(resultado, limite)

    @classmethod
    def _extrair_posts_dom_vivo(
        cls,
        driver: Any,
        usuario: str,
        limite: int,
    ) -> list[ScrapedPost]:
        """Extrai posts do DOM vivo via JavaScript.

        Não depende da tag ``article``. O ponto de ancoragem é o link
        semântico ``/<usuario>/status/<snowflake>``. Primeiro usa links que
        contêm ``time`` (link principal do tweet) e depois complementa com
        qualquer status link do perfil caso o X altere o cabeçalho.
        """
        script = r"""
            const alvo = String(arguments[0] || '').toLowerCase();
            const re = /^\/([^/]+)\/status\/(\d+)/i;
            const candidatos = [];
            const pushUnique = (a) => {
                if (!a) return;
                let path = '';
                try { path = new URL(a.getAttribute('href') || '', location.origin).pathname; }
                catch (_) { return; }
                const m = path.match(re);
                if (!m || m[1].toLowerCase() !== alvo) return;
                if (candidatos.some(x => x.postId === m[2])) return;
                candidatos.push({anchor: a, postId: m[2]});
            };

            // O link de data/hora é o melhor identificador do tweet principal.
            for (const time of document.querySelectorAll('time')) {
                pushUnique(time.closest('a[href*="/status/"]'));
            }
            // Fallback para mudanças de markup onde o time deixe de ser um filho do link.
            for (const a of document.querySelectorAll('a[href*="/status/"]')) {
                pushUnique(a);
            }

            const rows = [];
            for (const item of candidatos) {
                const a = item.anchor;
                let root = a.closest('[data-testid="cellInnerDiv"]')
                    || a.closest('[data-testid="tweet"]')
                    || a.closest('[role="article"]')
                    || a.closest('article');

                // Se o X removeu os containers semânticos, sobe até achar o
                // menor ancestral que contenha o texto do tweet.
                if (!root) {
                    let node = a.parentElement;
                    for (let i = 0; i < 10 && node; i++, node = node.parentElement) {
                        if (node.querySelector && node.querySelector('[data-testid="tweetText"]')) {
                            root = node;
                            break;
                        }
                    }
                }
                if (!root) root = a.parentElement;

                const firstTime = root && root.querySelector ? root.querySelector('time') : null;
                const thisTime = a.querySelector ? a.querySelector('time') : null;
                // Evita capturar status de tweet citado dentro do tweet principal.
                if (firstTime && thisTime && firstTime !== thisTime) continue;

                const textNode = root && root.querySelector
                    ? root.querySelector('[data-testid="tweetText"]')
                    : null;
                const socialNode = root && root.querySelector
                    ? root.querySelector('[data-testid="socialContext"]')
                    : null;
                const timeNode = thisTime || firstTime;
                const metricText = (testid) => {
                    if (!root || !root.querySelector) return '';
                    const el = root.querySelector(`[data-testid="${testid}"]`);
                    if (!el) return '';
                    return el.getAttribute('aria-label') || el.innerText || '';
                };
                const media = [];
                const mediaSeen = new Set();
                const pushMedia = (type, rawUrl) => {
                    const src = String(rawUrl || '').trim();
                    if (!src || mediaSeen.has(src)) return;
                    let parsed;
                    try { parsed = new URL(src, location.origin); }
                    catch (_) { return; }

                    // Perfis/emoji também usam <img>, mas a mídia do tweet é
                    // servida principalmente por pbs.twimg.com/media ou pelos
                    // thumbnails de vídeo do próprio X.
                    const host = parsed.hostname.toLowerCase();
                    const path = parsed.pathname.toLowerCase();
                    const isTweetMedia = host === 'pbs.twimg.com' && (
                        path.includes('/media/')
                        || path.includes('/ext_tw_video_thumb/')
                        || path.includes('/amplify_video_thumb/')
                        || path.includes('/tweet_video_thumb/')
                    );
                    if (!isTweetMedia) return;

                    mediaSeen.add(src);
                    media.push({type, url: src});
                };

                if (root && root.querySelectorAll) {
                    for (const img of root.querySelectorAll('img')) {
                        const src = img.currentSrc || img.src || '';
                        pushMedia('photo', src);
                    }
                    for (const video of root.querySelectorAll('video[poster]')) {
                        pushMedia('video_thumbnail', video.getAttribute('poster') || '');
                    }
                }

                rows.push({
                    href: a.getAttribute('href') || '',
                    post_id: item.postId,
                    datetime: timeNode ? (timeNode.getAttribute('datetime') || '') : '',
                    text: textNode ? (textNode.innerText || textNode.textContent || '') : '',
                    social_context: socialNode ? (socialNode.innerText || socialNode.textContent || '') : '',
                    root_text: root ? (root.innerText || root.textContent || '') : '',
                    metrics: {
                        reply: metricText('reply'),
                        retweet: metricText('retweet'),
                        like: metricText('like'),
                    },
                    media: media,
                });
            }
            return rows;
        """
        try:
            rows = driver.execute_script(script, usuario)
        except Exception as exc:
            logger.debug("[@%s] falha ao extrair status links do DOM vivo: %s", usuario, exc)
            return []
        return cls._normalizar_posts_dom_vivo(rows, usuario, limite)

    @staticmethod
    def _contar_articles_dom(driver: Any) -> int:
        seletores = (
            'article[data-testid="tweet"]',
            'article[role="article"]',
        )
        maior = 0
        for seletor in seletores:
            try:
                maior = max(maior, len(driver.find_elements(By.CSS_SELECTOR, seletor)))
            except Exception:
                continue
        return maior

    @staticmethod
    def _ordenar_posts(posts: list[ScrapedPost], limite: int) -> list[ScrapedPost]:
        unicos: dict[str, ScrapedPost] = {}
        for post in posts:
            atual = unicos.get(post.post_id)
            if atual is None:
                unicos[post.post_id] = post
                continue

            # Fontes diferentes do mesmo DOM podem completar partes distintas
            # do tweet. Em especial, o parser por status-link costuma obter o
            # texto antes da mídia lazy-loaded, enquanto o parser HTML pode
            # encontrar a imagem alguns instantes depois. Mescla os campos em
            # vez de descartar a segunda leitura do mesmo post.
            if not atual.texto and post.texto:
                atual.texto = post.texto
            if not atual.midia and post.midia:
                atual.midia = post.midia
            if atual.publicado_em is None and post.publicado_em is not None:
                atual.publicado_em = post.publicado_em
            if not atual.autor_nome and post.autor_nome:
                atual.autor_nome = post.autor_nome
            if not atual.autor_usuario and post.autor_usuario:
                atual.autor_usuario = post.autor_usuario
            if not atual.autor_foto_url and post.autor_foto_url:
                atual.autor_foto_url = post.autor_foto_url
            atual.autor_verificado = atual.autor_verificado or post.autor_verificado

        ordenados = sorted(
            unicos.values(),
            key=lambda item: (
                item.publicado_em or datetime.min.replace(tzinfo=timezone.utc),
                int(item.post_id) if item.post_id.isdigit() else 0,
            ),
            reverse=True,
        )
        return ordenados[:limite]

    @staticmethod
    def _tem_indicio_de_midia(post: ScrapedPost) -> bool:
        texto = (post.texto or "").lower()
        return "pic.twitter.com/" in texto

    @staticmethod
    def _normalizar_url_midia(raw_url: str) -> str | None:
        url = unescape(str(raw_url or "").strip()).replace("\\u0026", "&")
        if not url:
            return None
        try:
            parsed = urlsplit(url)
        except Exception:
            return None
        if parsed.scheme != "https" or parsed.hostname != "pbs.twimg.com":
            return None
        path = parsed.path.lower()
        if not any(
            trecho in path
            for trecho in (
                "/media/",
                "/ext_tw_video_thumb/",
                "/amplify_video_thumb/",
                "/tweet_video_thumb/",
            )
        ):
            return None
        return url

    def _extrair_midia_pagina_tweet(
        self,
        driver: Any,
        post: ScrapedPost,
    ) -> list[dict[str, Any]]:
        """Abre apenas o tweet selecionado e força o carregamento da mídia.

        A timeline do X é virtualizada e pode disponibilizar o link/status antes
        de montar a imagem. Por isso esta segunda passagem só é executada para os
        três posts selecionados que aparentam conter mídia e ainda chegaram com
        ``midia=[]``.
        """
        logger.info("[media] GET %s", post.url)
        try:
            driver.get(post.url)
        except Exception as exc:
            logger.warning("[media] navegação falhou para %s: %s", post.post_id, exc)

        try:
            WebDriverWait(driver, 8.0, poll_frequency=0.4).until(
                lambda d: d.execute_script("return document.readyState")
                in {"interactive", "complete"}
            )
        except Exception:
            pass

        # Centraliza o tweet principal para disparar o lazy-load das fotos.
        try:
            driver.execute_script(
                r"""
                const id = String(arguments[0]);
                const anchors = Array.from(document.querySelectorAll('a[href*="/status/"]'));
                const a = anchors.find(el => {
                    try {
                        const u = new URL(el.getAttribute('href') || '', location.origin);
                        return u.pathname.includes('/status/' + id) && !!el.querySelector('time');
                    } catch (_) { return false; }
                }) || anchors.find(el => (el.getAttribute('href') || '').includes('/status/' + id));
                const root = a && (
                    a.closest('[data-testid="cellInnerDiv"]') ||
                    a.closest('[data-testid="tweet"]') ||
                    a.closest('[role="article"]') ||
                    a.closest('article')
                );
                if (root && root.scrollIntoView) root.scrollIntoView({block: 'center'});
                """,
                post.post_id,
            )
        except Exception:
            pass

        # Se o tweet contém pic.twitter.com, esperamos especificamente por uma
        # URL pbs.twimg.com. Isso evita considerar o texto pronto como sinal de
        # que a mídia lazy-loaded também terminou de renderizar.
        try:
            WebDriverWait(driver, 6.0, poll_frequency=0.5).until(
                lambda d: bool(
                    d.execute_script(
                        r"""
                        const sels = [
                            'img[src*="pbs.twimg.com/media/"]',
                            'img[src*="pbs.twimg.com/amplify_video_thumb/"]',
                            'img[src*="pbs.twimg.com/ext_tw_video_thumb/"]',
                            'img[src*="pbs.twimg.com/tweet_video_thumb/"]',
                            'video[poster*="pbs.twimg.com/"]',
                            'meta[property="og:image"][content*="pbs.twimg.com/"]',
                            'meta[name="twitter:image"][content*="pbs.twimg.com/"]'
                        ];
                        return sels.some(s => !!document.querySelector(s));
                        """
                    )
                )
            )
        except TimeoutException:
            logger.info("[media] timeout aguardando mídia do post %s", post.post_id)

        script = r"""
            const postId = String(arguments[0]);
            const urls = [];
            const seen = new Set();
            const add = (raw, type) => {
                const value = String(raw || '').trim();
                if (!value || seen.has(value)) return;
                let u;
                try { u = new URL(value, location.origin); } catch (_) { return; }
                const host = u.hostname.toLowerCase();
                const path = u.pathname.toLowerCase();
                if (host !== 'pbs.twimg.com') return;
                if (!(
                    path.includes('/media/') ||
                    path.includes('/ext_tw_video_thumb/') ||
                    path.includes('/amplify_video_thumb/') ||
                    path.includes('/tweet_video_thumb/')
                )) return;
                seen.add(value);
                urls.push({type: type || 'photo', url: value});
            };

            const anchors = Array.from(document.querySelectorAll('a[href*="/status/"]'));
            const a = anchors.find(el => {
                try {
                    const u = new URL(el.getAttribute('href') || '', location.origin);
                    return u.pathname.includes('/status/' + postId) && !!el.querySelector('time');
                } catch (_) { return false; }
            }) || anchors.find(el => (el.getAttribute('href') || '').includes('/status/' + postId));
            const root = a && (
                a.closest('[data-testid="cellInnerDiv"]') ||
                a.closest('[data-testid="tweet"]') ||
                a.closest('[role="article"]') ||
                a.closest('article')
            );
            const scope = root || document;

            for (const img of scope.querySelectorAll('img')) {
                add(img.currentSrc || img.src || img.getAttribute('src') || '', 'photo');
                const srcset = img.getAttribute('srcset') || '';
                if (srcset) {
                    for (const candidate of srcset.split(',')) {
                        add(candidate.trim().split(/\s+/)[0] || '', 'photo');
                    }
                }
            }
            for (const video of scope.querySelectorAll('video[poster]')) {
                add(video.getAttribute('poster') || '', 'video_thumbnail');
            }

            // Metatags são um fallback útil na página canônica do tweet.
            for (const meta of document.querySelectorAll(
                'meta[property="og:image"], meta[name="twitter:image"]'
            )) {
                add(meta.getAttribute('content') || '', 'photo');
            }

            // Caso o root virtualizado ainda não tenha mídia, usa todos os
            // elementos pbs da página, sempre filtrando pelos paths de mídia.
            if (urls.length === 0) {
                for (const img of document.querySelectorAll('img[src*="pbs.twimg.com/"]')) {
                    add(img.currentSrc || img.src || img.getAttribute('src') || '', 'photo');
                }
                for (const video of document.querySelectorAll('video[poster*="pbs.twimg.com/"]')) {
                    add(video.getAttribute('poster') || '', 'video_thumbnail');
                }
            }
            return urls;
        """

        encontrados: list[dict[str, Any]] = []
        try:
            rows = driver.execute_script(script, post.post_id) or []
            if isinstance(rows, list):
                vistos: set[str] = set()
                for item in rows:
                    if not isinstance(item, dict):
                        continue
                    url = self._normalizar_url_midia(str(item.get("url") or ""))
                    if not url or url in vistos:
                        continue
                    vistos.add(url)
                    tipo = str(item.get("type") or "photo")
                    encontrados.append({"type": tipo, "url": url})
        except Exception as exc:
            logger.debug("[media] JS falhou para %s: %s", post.post_id, exc)

        # Último fallback: algumas respostas iniciais do X já carregam as URLs
        # da mídia no HTML/JSON antes de criarem os elementos <img>.
        if not encontrados:
            try:
                html = self._outer_html(driver)
            except Exception:
                html = ""
            padrao = re.compile(
                r'https://pbs\.twimg\.com/(?:media|ext_tw_video_thumb|amplify_video_thumb|tweet_video_thumb)/[^"\'<>\\\s]+'
            )
            vistos: set[str] = set()
            for raw in padrao.findall(html or ""):
                url = self._normalizar_url_midia(raw)
                if not url or url in vistos:
                    continue
                vistos.add(url)
                encontrados.append({"type": "photo", "url": url})
                if len(encontrados) >= 4:
                    break

        logger.info("[media] post=%s encontradas=%s", post.post_id, len(encontrados))
        return encontrados[:4]

    def _enriquecer_midia_posts(
        self,
        driver: Any,
        posts: list[ScrapedPost],
    ) -> list[ScrapedPost]:
        for post in posts:
            if post.midia or not self._tem_indicio_de_midia(post):
                continue
            try:
                midia = self._extrair_midia_pagina_tweet(driver, post)
            except Exception as exc:
                logger.warning("[media] falha no post %s: %s", post.post_id, exc)
                continue
            if midia:
                post.midia = midia
        return posts

    def _salvar_debug_falha(
        self,
        conta: ContaScrape,
        driver: Any,
        html: str,
        body_text: str,
        motivo: str | None,
    ) -> str | None:
        if not settings.x_scrape_debug_enabled:
            return None

        debug_dir = Path(settings.x_scrape_debug_dir)
        if not debug_dir.is_absolute():
            debug_dir = BACKEND_DIR / debug_dir
        debug_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = debug_dir / f"{conta.usuario}_{timestamp}"
        html_path = base.with_suffix(".html")
        txt_path = base.with_suffix(".txt")
        png_path = base.with_suffix(".png")

        try:
            html_path.write_text(html or "", encoding="utf-8", errors="ignore")
        except Exception:
            logger.exception("[@%s] falha ao salvar HTML de debug", conta.usuario)

        try:
            current_url = driver.current_url or ""
        except Exception:
            current_url = ""
        try:
            titulo = driver.title or ""
        except Exception:
            titulo = ""

        try:
            txt_path.write_text(
                "\n".join(
                    [
                        f"usuario=@{conta.usuario}",
                        f"url={current_url}",
                        f"title={titulo}",
                        f"motivo={motivo or '-'}",
                        "",
                        "--- BODY TEXT ---",
                        body_text or "",
                    ]
                ),
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            logger.exception("[@%s] falha ao salvar TXT de debug", conta.usuario)

        try:
            driver.save_screenshot(str(png_path))
        except Exception:
            logger.exception("[@%s] falha ao salvar screenshot de debug", conta.usuario)

        logger.error(
            "[@%s] debug salvo em %s (.html/.txt/.png)",
            conta.usuario,
            base,
        )
        return str(base)

    def _contas_ativas(self, usuario: str | None = None) -> list[ContaScrape]:
        filtros = ["ativo = true"]
        params: list[Any] = []
        if usuario:
            filtros.append("lower(usuario) = lower(%s)")
            params.append(usuario.lstrip("@"))

        sql = f"""
            select id::text, nome, usuario, foto_url, ultimo_post_id
            from public.contas_x
            where {' and '.join(filtros)}
            order by case when lower(usuario) = 'atletico' then 0 else 1 end,
                     md5(lower(usuario))
        """
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                contas = [ContaScrape(*row) for row in cur.fetchall()]
        logger.info("[supabase] %s conta(s) ativa(s) carregada(s)", len(contas))
        return contas

    def _scrape_posts(self, conta: ContaScrape) -> list[ScrapedPost]:
        driver = self._driver()
        url = f"https://x.com/{conta.usuario}"
        logger.info("[@%s] [x.com] UC GET %s", conta.usuario, url)

        # Em headless, driver.get() tende a ser mais previsível que
        # uc_open_with_reconnect(), que foi criado principalmente para fluxos
        # interativos/anti-bot. Mantemos UC no driver; apenas a navegação muda.
        try:
            if settings.x_scrape_headless:
                driver.get(url)
            elif hasattr(driver, "uc_open_with_reconnect"):
                driver.uc_open_with_reconnect(url, 4)
            else:
                driver.get(url)
        except Exception as exc:
            logger.warning(
                "[@%s] navegação inicial retornou erro; tentando analisar DOM: %s",
                conta.usuario,
                exc,
            )

        limite = max(1, settings.x_scrape_posts_per_account)
        max_tentativas = max(4, settings.x_scrape_max_scrolls + 1)
        coletados: list[ScrapedPost] = []
        current_url = ""
        html = ""
        body_text = ""
        bloqueio: str | None = None

        # Aguarda a página atingir interactive/complete sem depender de sleep fixo.
        try:
            WebDriverWait(
                driver,
                max(5.0, min(settings.x_scrape_page_timeout_seconds, 20.0)),
                poll_frequency=0.5,
            ).until(
                lambda d: d.execute_script("return document.readyState")
                in {"interactive", "complete"}
            )
        except Exception:
            logger.info("[@%s] document.readyState não estabilizou; prosseguindo", conta.usuario)

        # O X pode renderizar os tweets sem uma tag <article>. O log real
        # confirmou posts visíveis no body com articles=0. Por isso o sinal
        # primário passa a ser a presença de links /<usuario>/status/<id>.
        try:
            WebDriverWait(
                driver,
                max(5.0, settings.x_scrape_timeline_wait_seconds),
                poll_frequency=0.75,
            ).until(
                lambda d: self._status_links_dom(d, conta.usuario) > 0
                or self._contar_articles_dom(d) > 0
            )
            logger.info("[@%s] timeline detectada via status link/DOM", conta.usuario)
        except TimeoutException:
            logger.warning(
                "[@%s] timeline não apareceu em %.1fs; iniciando diagnóstico/scroll",
                conta.usuario,
                settings.x_scrape_timeline_wait_seconds,
            )

        for tentativa in range(1, max_tentativas + 1):
            if tentativa > 1:
                time.sleep(max(0.5, settings.x_scrape_scroll_pause_seconds))

            try:
                current_url = driver.current_url or ""
            except Exception:
                current_url = ""
            html = self._outer_html(driver)
            body_text = self._body_text(driver)

            # Fonte principal: DOM vivo via JavaScript, ancorado em /status/.
            # Fallback: parser HTML legado, útil quando <article> voltar a existir.
            posts_live = self._extrair_posts_dom_vivo(
                driver,
                conta.usuario,
                limite=max(limite, 10),
            )
            posts_html = self.extrair_posts_html(
                html,
                conta.usuario,
                limite=max(limite, 10),
            )
            coletados.extend(posts_live)
            coletados.extend(posts_html)
            melhores = self._ordenar_posts(coletados, limite)
            articles = self._contar_articles_dom(driver)
            status_links = self._status_links_dom(driver, conta.usuario)
            bloqueio = self._detectar_bloqueio(html, body_text, current_url)

            logger.info(
                "[@%s] [x.com] tentativa=%s articles=%s status_links=%s "
                "posts_live=%s posts_html=%s acumulados=%s ids=%s url=%s",
                conta.usuario,
                tentativa,
                articles,
                status_links,
                len(posts_live),
                len(posts_html),
                len({post.post_id for post in coletados}),
                ",".join(post.post_id for post in melhores) or "-",
                current_url or "-",
            )

            if len(melhores) >= limite:
                return self._enriquecer_midia_posts(driver, melhores)

            if bloqueio and not posts_live and not posts_html:
                logger.warning("[@%s] X sinalizou: %s", conta.usuario, bloqueio)

            if tentativa < max_tentativas:
                try:
                    # Scroll incremental baseado na viewport reduz saltos grandes
                    # que podem fazer a timeline virtualizada descartar os primeiros
                    # artigos antes de o parser capturá-los.
                    driver.execute_script(
                        "window.scrollBy({top: Math.max(500, window.innerHeight * 0.72), "
                        "left: 0, behavior: 'smooth'});"
                    )
                except Exception:
                    try:
                        driver.execute_script("window.scrollBy(0, 850);")
                    except Exception:
                        pass

                try:
                    WebDriverWait(
                        driver,
                        max(2.0, settings.x_scrape_scroll_pause_seconds + 1.0),
                        poll_frequency=0.5,
                    ).until(
                        lambda d: self._status_links_dom(d, conta.usuario) > 0
                        or self._contar_articles_dom(d) > 0
                    )
                except TimeoutException:
                    pass

        melhores = self._ordenar_posts(coletados, limite)
        if melhores:
            return self._enriquecer_midia_posts(driver, melhores)

        titulo = ""
        try:
            titulo = driver.title or ""
        except Exception:
            pass

        debug_base = self._salvar_debug_falha(
            conta,
            driver,
            html,
            body_text,
            bloqueio,
        )
        body_resumo = re.sub(r"\s+", " ", body_text)[:300] or "(body vazio)"
        debug_info = f" Debug: {debug_base}.html/.txt/.png." if debug_base else ""

        status_links_final = self._status_links_dom(driver, conta.usuario)
        articles_final = self._contar_articles_dom(driver)
        if bloqueio:
            raise XScrapeBlockedError(
                f"{bloqueio}. articles={articles_final} status_links={status_links_final} "
                f"title={titulo!r} url={current_url or '-'}; "
                f"body={body_resumo!r}.{debug_info}"
            )

        raise XScrapeError(
            "Nenhuma publicação própria foi encontrada após espera explícita e scroll "
            "incremental no DOM público do X via SeleniumBase UC. "
            f"articles={articles_final} status_links={status_links_final} "
            f"title={titulo!r} url={current_url or '-'}; "
            f"body={body_resumo!r}.{debug_info}"
        )

    @staticmethod
    def _atualizar_perfil_por_post(conta: ContaScrape, post: ScrapedPost) -> None:
        if not post.autor_foto_url and not post.autor_nome:
            return
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.contas_x
                       set foto_url = coalesce(%s, foto_url),
                           nome = case
                               when %s is not null and %s <> '' then %s
                               else nome
                           end
                     where id = %s::uuid
                    """,
                    (
                        post.autor_foto_url,
                        post.autor_nome,
                        post.autor_nome,
                        post.autor_nome,
                        conta.id,
                    ),
                )
            conn.commit()

    def _oembed(self, url: str) -> str:
        logger.info("[oEmbed] GET %s", url)
        try:
            response = self.oembed_client.get(
                X_OEMBED_URL,
                params={
                    "url": url,
                    "omit_script": "true",
                    "dnt": "true",
                    "hide_thread": "true",
                    "lang": "pt",
                    "theme": "light",
                    "maxwidth": "550",
                },
            )
        except httpx.TimeoutException as exc:
            raise XScrapeError(f"oEmbed timeout para {url}") from exc
        except httpx.RequestError as exc:
            raise XScrapeError(f"oEmbed falhou para {url}: {exc}") from exc

        if not response.is_success:
            detalhe = (response.text or "").strip().replace("\n", " ")[:700]
            raise XScrapeError(
                f"oEmbed HTTP {response.status_code} para {url}: {detalhe or 'sem corpo'}"
            )
        try:
            payload = response.json()
        except Exception as exc:
            raise XScrapeError(f"oEmbed retornou JSON inválido para {url}") from exc

        html = self.sanitizar_oembed_html(payload.get("html") if isinstance(payload, dict) else None)
        if not html or "twitter-tweet" not in html or "<blockquote" not in html.lower():
            raise XScrapeError(f"oEmbed retornou HTML inesperado para {url}")
        logger.info("[oEmbed] HTML nativo validado para %s", url)
        return html

    @staticmethod
    def _post_cache_status(post_id: str) -> tuple[bool, bool, str | None]:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        true,
                        (embed_html is not null and embed_status = 'ok'),
                        embed_html
                    from public.posts_x
                    where post_id = %s
                    limit 1
                    """,
                    (post_id,),
                )
                row = cur.fetchone()
        if row is None:
            return False, False, None
        return bool(row[0]), bool(row[1]), row[2]

    def _upsert_post(self, conta: ContaScrape, post: ScrapedPost) -> tuple[bool, bool]:
        existe, embed_ja_ok, embed_cache = self._post_cache_status(post.post_id)
        embed_html: str | None = None
        embed_status = "ok" if embed_ja_ok else "erro"
        embed_atualizado_em = None
        oembed_erro: str | None = None

        if embed_ja_ok:
            logger.info(
                "[@%s] post %s já possui embed válido; oEmbed não será chamado novamente",
                conta.usuario,
                post.post_id,
            )
        else:
            try:
                embed_html = self._oembed(post.url)
                embed_status = "ok"
                embed_atualizado_em = datetime.now(timezone.utc)
            except Exception as exc:
                oembed_erro = str(exc)[:1500]
                logger.exception(
                    "[@%s] oEmbed falhou para post %s: %s",
                    conta.usuario,
                    post.post_id,
                    exc,
                )

        html_para_texto = embed_html or embed_cache
        if not post.texto and html_para_texto:
            texto_oembed = self.texto_do_oembed_html(html_para_texto)
            if texto_oembed:
                post.texto = texto_oembed
                logger.info(
                    "[@%s] post %s: texto recuperado do oEmbed",
                    conta.usuario,
                    post.post_id,
                )

        metadados: dict[str, Any] = {
            "origem": "x_seleniumbase_uc_scrape",
            "scrape_sem_login": True,
            "scrape_cache_agressivo": True,
            "autor_verificado": post.autor_verificado,
        }
        if oembed_erro:
            metadados["oembed_erro"] = oembed_erro

        sql = """
            insert into public.posts_x (
                conta_id, post_id, url, texto, publicado_em, coletado_em,
                metadados, metricas, midia, embed_html, embed_status,
                embed_atualizado_em, ativo
            )
            values (%s::uuid, %s, %s, %s, %s, now(), %s, %s, %s, %s, %s, %s, true)
            on conflict (post_id) do update set
                conta_id = excluded.conta_id,
                url = excluded.url,
                texto = coalesce(excluded.texto, public.posts_x.texto),
                publicado_em = coalesce(excluded.publicado_em, public.posts_x.publicado_em),
                metadados = coalesce(public.posts_x.metadados, '{}'::jsonb) || excluded.metadados,
                metricas = excluded.metricas,
                midia = case when excluded.midia = '[]'::jsonb then public.posts_x.midia else excluded.midia end,
                embed_html = coalesce(excluded.embed_html, public.posts_x.embed_html),
                embed_status = case
                    when excluded.embed_html is not null then 'ok'
                    when public.posts_x.embed_html is not null and public.posts_x.embed_status = 'ok' then 'ok'
                    else excluded.embed_status
                end,
                embed_atualizado_em = coalesce(excluded.embed_atualizado_em, public.posts_x.embed_atualizado_em),
                ativo = true
            returning (xmax = 0) as inserido,
                      (embed_html is not null and embed_status = 'ok') as embed_ok
        """
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        conta.id,
                        post.post_id,
                        post.url,
                        post.texto,
                        post.publicado_em,
                        Jsonb(metadados),
                        Jsonb(post.metricas),
                        Jsonb(post.midia),
                        embed_html,
                        embed_status,
                        embed_atualizado_em,
                    ),
                )
                inserido, embed_ok = cur.fetchone()
            conn.commit()

        logger.info(
            "[@%s] [supabase] post=%s inserido=%s embed_ok=%s midia=%s",
            conta.usuario,
            post.post_id,
            bool(inserido),
            bool(embed_ok),
            len(post.midia),
        )
        return bool(inserido) and not existe, bool(embed_ok)

    def _finalizar_conta(
        self,
        conta: ContaScrape,
        status: str,
        erro: str | None,
        ultimo_post_id: str | None = None,
    ) -> None:
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.contas_x
                       set ultimo_post_id = coalesce(%s, ultimo_post_id),
                           ultima_sincronizacao = now(),
                           status_sync = %s,
                           sync_erro = %s
                     where id = %s::uuid
                    """,
                    (ultimo_post_id, status, erro, conta.id),
                )
            conn.commit()

    def sincronizar_conta(self, conta: ContaScrape) -> dict:
        logger.info("[@%s] início | fonte=x.com SeleniumBase UC público", conta.usuario)
        novos = 0
        embeds_atualizados = 0
        try:
            posts = self._scrape_posts(conta)
            logger.info("[@%s] descoberta retornou %s publicação(ões)", conta.usuario, len(posts))

            for post in posts:
                inserido, embed_ok = self._upsert_post(conta, post)
                novos += int(inserido)
                embeds_atualizados += int(embed_ok)

            ids = [post.post_id for post in posts if post.post_id.isdigit()]
            ultimo = max(ids, key=int) if ids else conta.ultimo_post_id
            self._finalizar_conta(conta, "ok", None, ultimo)
            logger.info(
                "[@%s] fim | novos=%s embeds_ok=%s status=ok",
                conta.usuario,
                novos,
                embeds_atualizados,
            )
            return {
                "usuario": conta.usuario,
                "novos": novos,
                "embeds_atualizados": embeds_atualizados,
                "status": "ok",
                "erro": None,
            }
        except Exception as exc:
            erro = str(exc)[:1500]
            logger.exception("[@%s] coleta pública falhou: %s", conta.usuario, exc)
            self._finalizar_conta(conta, "erro", erro)
            return {
                "usuario": conta.usuario,
                "novos": novos,
                "embeds_atualizados": embeds_atualizados,
                "status": "erro",
                "erro": erro,
            }

    def sincronizar_todas(self, usuario: str | None = None) -> dict:
        contas = self._contas_ativas(usuario=usuario)
        if usuario and not contas:
            raise RuntimeError(f"Conta @{usuario.lstrip('@')} não está cadastrada/ativa no Supabase.")

        logger.info("[job] início | fonte=x_seleniumbase_uc_scrape | contas=%s", len(contas))
        resultados: list[dict] = []
        for indice, conta in enumerate(contas):
            logger.info("[job] tentativa explícita de coleta para @%s", conta.usuario)
            resultados.append(self.sincronizar_conta(conta))
            if indice < len(contas) - 1:
                atraso = max(30.0, settings.x_scrape_delay_between_accounts_seconds)
                jitter = min(5.0, max(0.0, atraso * 0.15))
                espera = max(0.0, atraso + random.uniform(-jitter, jitter))
                logger.info("[job] aguardando %.1fs antes da próxima conta", espera)
                time.sleep(espera)

        resumo = {
            "contas": len(resultados),
            "novos": sum(item["novos"] for item in resultados),
            "embeds_atualizados": sum(item["embeds_atualizados"] for item in resultados),
            "resultados": resultados,
        }
        logger.info(
            "[job] fim | contas=%s novos=%s embeds=%s erros=%s",
            resumo["contas"],
            resumo["novos"],
            resumo["embeds_atualizados"],
            sum(1 for item in resultados if item["status"] != "ok"),
        )
        return resumo
