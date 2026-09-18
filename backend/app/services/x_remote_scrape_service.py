from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote

from app.core.config import get_settings
from app.services.x_collector_store import remote_call
from app.services.x_scrape_service import ContaScrape, ScrapedPost, XScrapeService

logger = logging.getLogger("central_galo.x_remote")
settings = get_settings()


class RemoteXScrapeService(XScrapeService):
    def _scrape_posts(self, conta: ContaScrape) -> list[ScrapedPost]:
        syndication_url = (
            "https://syndication.twitter.com/srv/timeline-profile/screen-name/"
            + quote(conta.usuario, safe="")
        )

        try:
            logger.info(
                "[@%s] [syndication] GET %s",
                conta.usuario,
                syndication_url,
            )
            response = self.oembed_client.get(
                syndication_url,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": self.user_agent,
                },
            )

            if response.is_success:
                posts = self.extrair_posts_syndication_html(
                    response.text,
                    conta.usuario,
                    limite=max(1, settings.x_scrape_posts_per_account),
                )
                if posts:
                    logger.info(
                        "[@%s] [syndication] %s publicação(ões) encontrada(s)",
                        conta.usuario,
                        len(posts),
                    )
                    return posts

            logger.warning(
                "[@%s] syndication indisponível/sem posts; fallback Selenium | HTTP=%s",
                conta.usuario,
                response.status_code,
            )
        except Exception as exc:
            logger.warning(
                "[@%s] syndication falhou (%s); fallback Selenium",
                conta.usuario,
                exc,
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
