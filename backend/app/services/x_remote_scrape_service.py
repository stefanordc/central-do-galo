from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote, unquote, urlparse

from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.services.x_collector_store import remote_call
from app.services.x_scrape_service import ContaScrape, ScrapedPost, XScrapeService

logger = logging.getLogger("central_galo.x_remote")
settings = get_settings()


class RemoteXScrapeService(XScrapeService):
    @staticmethod
    def _rss_media_url(src: str) -> str | None:
        valor = (src or "").strip()
        if not valor:
            return None

        try:
            parsed = urlparse(valor)
        except Exception:
            return None

        if parsed.hostname == "pbs.twimg.com":
            return valor.replace("http://", "https://", 1)

        marcador = "/pic/"
        if marcador not in parsed.path:
            return None

        bruto = unquote(parsed.path.split(marcador, 1)[1]).lstrip("/")
        if bruto.startswith("media/"):
            nome = bruto.split("/", 1)[1]
            if nome:
                return f"https://pbs.twimg.com/media/{nome}"

        return None

    @classmethod
    def _parse_rss_posts(
        cls,
        xml_text: str,
        usuario: str,
        limite: int,
    ) -> list[ScrapedPost]:
        root = ET.fromstring(xml_text)
        dc_creator = "{http://purl.org/dc/elements/1.1/}creator"
        alvo = usuario.lower().lstrip("@")
        resultado: list[ScrapedPost] = []
        vistos: set[str] = set()

        for item in root.findall(".//item"):
            titulo = (item.findtext("title") or "").strip()
            creator = (item.findtext(dc_creator) or "").strip().lstrip("@")

            if creator and creator.lower() != alvo:
                continue

            titulo_normalizado = titulo.lower()
            if (
                titulo_normalizado.startswith("r to @")
                or titulo_normalizado.startswith("rt by @")
                or titulo_normalizado.startswith("retweet by @")
            ):
                continue

            post_id = (item.findtext("guid") or "").strip()
            if not post_id.isdigit() or post_id in vistos:
                continue
            vistos.add(post_id)

            publicado_em = None
            pub_date = (item.findtext("pubDate") or "").strip()
            if pub_date:
                try:
                    publicado_em = parsedate_to_datetime(pub_date)
                    if publicado_em.tzinfo is None:
                        publicado_em = publicado_em.replace(tzinfo=timezone.utc)
                except Exception:
                    publicado_em = None

            descricao = item.findtext("description") or ""
            soup = BeautifulSoup(descricao, "html.parser")
            midia: list[dict] = []
            urls_midia: set[str] = set()

            for img in soup.find_all("img"):
                src = str(img.get("src") or "")
                media_url = cls._rss_media_url(src)
                if media_url and media_url not in urls_midia:
                    urls_midia.add(media_url)
                    midia.append({"type": "photo", "url": media_url})

            texto = titulo or soup.get_text(" ", strip=True) or None

            resultado.append(
                ScrapedPost(
                    post_id=post_id,
                    url=f"https://x.com/{usuario}/status/{post_id}",
                    texto=texto,
                    publicado_em=publicado_em,
                    metricas={},
                    midia=midia,
                )
            )

            if len(resultado) >= limite:
                break

        resultado.sort(
            key=lambda item: (
                item.publicado_em or datetime.min.replace(tzinfo=timezone.utc),
                int(item.post_id) if item.post_id.isdigit() else 0,
            ),
            reverse=True,
        )
        return resultado[:limite]

    def _scrape_posts_rss(self, conta: ContaScrape) -> list[ScrapedPost]:
        instancias = [
            "https://x.n0g.xyz",
            "https://tw.eir-nya.gay",
            "https://nitter.jaydenha.uk",
            "https://shitter.thepixora.com",
        ]
        limite = max(1, settings.x_scrape_posts_per_account)

        for base in instancias:
            rss_url = f"{base}/{quote(conta.usuario, safe='')}/rss"
            try:
                logger.info("[@%s] [rss] GET %s", conta.usuario, rss_url)
                response = self.oembed_client.get(
                    rss_url,
                    headers={
                        "Accept": "application/rss+xml,application/xml,text/xml",
                        "User-Agent": self.user_agent,
                    },
                )
                if not response.is_success:
                    logger.warning(
                        "[@%s] RSS %s respondeu HTTP %s",
                        conta.usuario,
                        base,
                        response.status_code,
                    )
                    continue

                texto = response.text.lstrip()
                if not texto.startswith("<?xml") and "<rss" not in texto[:300].lower():
                    logger.warning(
                        "[@%s] RSS %s retornou conteúdo não XML",
                        conta.usuario,
                        base,
                    )
                    continue

                posts = self._parse_rss_posts(
                    response.text,
                    conta.usuario,
                    limite=limite,
                )
                if posts:
                    logger.info(
                        "[@%s] [rss] %s publicação(ões) encontrada(s) via %s",
                        conta.usuario,
                        len(posts),
                        base,
                    )
                    return posts
            except Exception as exc:
                logger.warning(
                    "[@%s] RSS %s falhou: %s",
                    conta.usuario,
                    base,
                    exc,
                )

        return []

    def _scrape_posts(self, conta: ContaScrape) -> list[ScrapedPost]:
        try:
            resultado = remote_call(
                "syndication",
                usuario=conta.usuario,
            )
            status = int(resultado.get("status") or 0)
            html = str(resultado.get("html") or "")

            if bool(resultado.get("ok")) and html:
                posts = self.extrair_posts_syndication_html(
                    html,
                    conta.usuario,
                    limite=max(1, settings.x_scrape_posts_per_account),
                )
                if posts:
                    logger.info(
                        "[@%s] [syndication/supabase] %s publicação(ões) encontrada(s)",
                        conta.usuario,
                        len(posts),
                    )
                    return posts

            logger.info(
                "[@%s] syndication via Supabase indisponível/sem posts | HTTP=%s",
                conta.usuario,
                status,
            )
        except Exception as exc:
            logger.info(
                "[@%s] syndication via Supabase falhou: %s",
                conta.usuario,
                exc,
            )

        posts_rss = self._scrape_posts_rss(conta)
        if posts_rss:
            return posts_rss

        logger.warning(
            "[@%s] RSS indisponível; fallback final para Selenium/x.com",
            conta.usuario,
        )
        return super()._scrape_posts(conta)

    def _contas_ativas(self, usuario: str | None = None) -> list[ContaScrape]:
        resultado = remote_call(
            "list_accounts",
            usuario=(usuario or "").lstrip("@") or None,
        )
        contas = []
        for item in resultado.get("data", []):
            contas.append(
                ContaScrape(
                    id=str(item["id"]),
                    nome=str(item["nome"]),
                    usuario=str(item["usuario"]),
                    foto_url=item.get("foto_url"),
                    ultimo_post_id=item.get("ultimo_post_id"),
                )
            )
        logger.info("[supabase remoto] %s conta(s) ativa(s) carregada(s)", len(contas))
        return contas

    @staticmethod
    def _atualizar_perfil_por_post(conta: ContaScrape, post: ScrapedPost) -> None:
        if not post.autor_foto_url and not post.autor_nome:
            return

        remote_call(
            "update_profile",
            conta_id=conta.id,
            nome=post.autor_nome,
            foto_url=post.autor_foto_url,
        )

    @staticmethod
    def _post_cache_status(post_id: str) -> tuple[bool, bool, str | None]:
        resultado = remote_call("post_cache", post_id=post_id)
        return (
            bool(resultado.get("existe")),
            bool(resultado.get("embed_ok")),
            resultado.get("embed_html"),
        )

    def _upsert_post(self, conta: ContaScrape, post: ScrapedPost) -> tuple[bool, bool]:
        existe, embed_ja_ok, embed_cache = self._post_cache_status(post.post_id)
        embed_html: str | None = None
        embed_status = "ok" if embed_ja_ok else "erro"
        embed_atualizado_em: datetime | None = None
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

        metadados = {
            "origem": "x_seleniumbase_uc_scrape",
            "scrape_sem_login": True,
            "scrape_cache_agressivo": True,
            "autor_verificado": post.autor_verificado,
        }
        if oembed_erro:
            metadados["oembed_erro"] = oembed_erro

        resultado = remote_call(
            "save_post",
            conta_id=conta.id,
            item={
                "post_id": post.post_id,
                "url": post.url,
                "texto": post.texto,
                "publicado_em": post.publicado_em.isoformat() if post.publicado_em else None,
                "metadados": metadados,
                "metricas": post.metricas,
                "midia": post.midia,
                "embed_html": embed_html,
                "embed_status": embed_status,
                "embed_atualizado_em": (
                    embed_atualizado_em.isoformat() if embed_atualizado_em else None
                ),
            },
        )

        return (
            bool(resultado.get("inserido")) and not existe,
            bool(resultado.get("embed_ok")),
        )

    def _finalizar_conta(
        self,
        conta: ContaScrape,
        status: str,
        erro: str | None,
        ultimo_post_id: str | None = None,
    ) -> None:
        remote_call(
            "finalize_account",
            conta_id=conta.id,
            status=status,
            erro=erro,
            ultimo_post_id=ultimo_post_id,
        )
