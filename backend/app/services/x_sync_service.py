from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup
from psycopg.types.json import Jsonb

from app.core.config import get_settings
from app.db.pool import pool

settings = get_settings()
logger = logging.getLogger("central_galo.x_sync")
logger.setLevel(logging.INFO)

X_API_BASE = "https://api.x.com/2"
X_OEMBED_URL = "https://publish.x.com/oembed"


class XSyncHttpError(RuntimeError):
    def __init__(
        self,
        etapa: str,
        status_code: int | None,
        mensagem: str,
        *,
        rate_limit_reset: str | None = None,
    ) -> None:
        self.etapa = etapa
        self.status_code = status_code
        self.rate_limit_reset = rate_limit_reset
        super().__init__(mensagem)


@dataclass
class ContaSync:
    id: str
    nome: str
    usuario: str
    x_user_id: str | None
    foto_url: str | None
    ultimo_post_id: str | None


class XSyncService:
    def __init__(self, bearer_token: str | None = None) -> None:
        self.bearer_token = (bearer_token or settings.x_bearer_token or "").strip()
        if not self.bearer_token:
            raise RuntimeError(
                "X_BEARER_TOKEN não configurado no backend. "
                "A coleta oficial do X não pode iniciar sem essa credencial."
            )

        self.client = httpx.Client(
            timeout=settings.x_sync_timeout_seconds,
            follow_redirects=True,
            headers={
                "Authorization": f"Bearer {self.bearer_token}",
                "User-Agent": "CentralDoGalo/1.0",
                "Accept": "application/json",
            },
        )
        self.oembed_client = httpx.Client(
            timeout=settings.x_sync_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": "CentralDoGalo/1.0", "Accept": "application/json"},
        )

    def close(self) -> None:
        self.client.close()
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
    def _resumo_resposta(response: httpx.Response) -> str:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                erros = payload.get("errors")
                if erros:
                    return str(erros)[:700]
                detail = payload.get("detail") or payload.get("title")
                if detail:
                    return str(detail)[:700]
        except Exception:
            pass
        texto = (response.text or "").strip().replace("\n", " ")
        return texto[:700] or "sem corpo de resposta"

    def _validar_http(self, response: httpx.Response, etapa: str) -> None:
        if response.is_success:
            return

        status = response.status_code
        detalhe = self._resumo_resposta(response)
        reset = response.headers.get("x-rate-limit-reset")

        if status == 401:
            motivo = "credencial X inválida, expirada ou não reconhecida"
        elif status == 403:
            motivo = "credencial sem permissão/acesso para este endpoint ou recurso"
        elif status == 429:
            motivo = "rate limit da X API atingido"
        else:
            motivo = f"HTTP {status}"

        complemento = f" | rate-limit-reset={reset}" if reset else ""
        mensagem = f"{etapa}: {motivo}. Resposta: {detalhe}{complemento}"
        raise XSyncHttpError(
            etapa=etapa,
            status_code=status,
            mensagem=mensagem,
            rate_limit_reset=reset,
        )

    def _get_json(
        self,
        client: httpx.Client,
        url: str,
        *,
        params: dict[str, Any] | None,
        etapa: str,
    ) -> dict:
        logger.info("[%s] GET %s", etapa, url)
        try:
            response = client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise XSyncHttpError(etapa, None, f"{etapa}: timeout ao acessar {url}") from exc
        except httpx.RequestError as exc:
            raise XSyncHttpError(
                etapa,
                None,
                f"{etapa}: falha de rede ao acessar {url}: {exc}",
            ) from exc

        logger.info("[%s] resposta HTTP %s", etapa, response.status_code)
        self._validar_http(response, etapa)

        try:
            payload = response.json()
        except Exception as exc:
            raise XSyncHttpError(
                etapa,
                response.status_code,
                f"{etapa}: resposta não é JSON válido.",
            ) from exc

        if not isinstance(payload, dict):
            raise XSyncHttpError(
                etapa,
                response.status_code,
                f"{etapa}: formato de resposta inesperado ({type(payload).__name__}).",
            )
        return payload

    def _contas_ativas(self, usuario: str | None = None) -> list[ContaSync]:
        filtros = ["ativo = true"]
        parametros: list[Any] = []
        if usuario:
            filtros.append("lower(usuario) = lower(%s)")
            parametros.append(usuario.lstrip("@"))

        sql = f"""
            select id::text, nome, usuario, x_user_id, foto_url, ultimo_post_id
            from public.contas_x
            where {' and '.join(filtros)}
            order by case when lower(usuario) = 'atletico' then 0 else 1 end,
                     md5(lower(usuario))
        """
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, parametros)
                contas = [ContaSync(*row) for row in cur.fetchall()]

        logger.info("[supabase] %s conta(s) ativa(s) carregada(s)%s", len(contas), f" para @{usuario.lstrip('@')}" if usuario else "")
        return contas

    def _resolver_usuario(self, conta: ContaSync) -> ContaSync:
        if conta.x_user_id and conta.foto_url:
            logger.info("[@%s] perfil já resolvido: x_user_id=%s", conta.usuario, conta.x_user_id)
            return conta

        logger.info("[@%s] resolvendo username na X API", conta.usuario)
        payload = self._get_json(
            self.client,
            f"{X_API_BASE}/users/by/username/{conta.usuario}",
            params={
                "user.fields": "id,name,username,profile_image_url,verified,verified_type"
            },
            etapa=f"@{conta.usuario} lookup",
        )
        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("id"):
            erros = payload.get("errors")
            raise RuntimeError(
                f"Perfil @{conta.usuario} não encontrado pela X API. errors={str(erros)[:700]}"
            )

        conta.x_user_id = str(data["id"])
        conta.nome = data.get("name") or conta.nome
        conta.foto_url = data.get("profile_image_url") or conta.foto_url

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    update public.contas_x
                       set x_user_id = %s,
                           nome = %s,
                           foto_url = %s,
                           status_sync = 'sincronizando',
                           sync_erro = null
                     where id = %s::uuid
                    """,
                    (conta.x_user_id, conta.nome, conta.foto_url, conta.id),
                )
            conn.commit()

        logger.info("[@%s] perfil resolvido e gravado no Supabase", conta.usuario)
        return conta

    def _buscar_posts_novos(self, conta: ContaSync) -> tuple[list[dict], dict[str, dict]]:
        params: dict[str, Any] = {
            "max_results": max(5, min(settings.x_sync_fetch_limit, 100)),
            "tweet.fields": "id,text,created_at,public_metrics,attachments",
            "expansions": "attachments.media_keys",
            "media.fields": "media_key,type,url,preview_image_url,width,height",
        }
        if conta.ultimo_post_id:
            params["since_id"] = conta.ultimo_post_id

        logger.info(
            "[@%s] buscando posts recentes%s",
            conta.usuario,
            f" após {conta.ultimo_post_id}" if conta.ultimo_post_id else " (primeira carga)",
        )
        payload = self._get_json(
            self.client,
            f"{X_API_BASE}/users/{conta.x_user_id}/tweets",
            params=params,
            etapa=f"@{conta.usuario} posts",
        )

        media_por_chave = {
            str(item.get("media_key")): item
            for item in (payload.get("includes", {}).get("media") or [])
            if item.get("media_key")
        }
        posts = payload.get("data") or []
        if not isinstance(posts, list):
            raise RuntimeError(f"@{conta.usuario}: campo data da X API não é uma lista.")
        logger.info("[@%s] %s post(s) retornado(s) pela X API", conta.usuario, len(posts))
        return posts, media_por_chave

    def _oembed(self, url: str) -> str:
        if "/status/" not in url or not url.startswith("https://x.com/"):
            raise RuntimeError(f"URL de post inválida para oEmbed: {url}")

        payload = self._get_json(
            self.oembed_client,
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
            etapa="oEmbed",
        )

        html = self.sanitizar_oembed_html(payload.get("html"))
        if not html:
            raise RuntimeError(f"oEmbed do X retornou HTML vazio para {url}.")
        if "twitter-tweet" not in html or "<blockquote" not in html.lower():
            raise RuntimeError(f"oEmbed do X retornou HTML inesperado para {url}.")

        logger.info("[oEmbed] HTML nativo validado para %s", url)
        return html

    @staticmethod
    def _midias_do_post(post: dict, media_por_chave: dict[str, dict]) -> list[dict]:
        chaves = ((post.get("attachments") or {}).get("media_keys") or [])
        resultado: list[dict] = []
        for chave in chaves:
            media = media_por_chave.get(str(chave))
            if media:
                resultado.append(media)
        return resultado

    def _upsert_post(
        self,
        conta: ContaSync,
        post: dict,
        media_por_chave: dict[str, dict],
    ) -> tuple[bool, bool]:
        post_id = str(post["id"])
        url = f"https://x.com/{conta.usuario}/status/{post_id}"
        embed_html: str | None = None
        embed_status = "erro"
        embed_atualizado_em = None
        oembed_erro: str | None = None

        logger.info("[@%s] processando post %s", conta.usuario, post_id)
        try:
            embed_html = self._oembed(url)
            embed_status = "ok"
            embed_atualizado_em = datetime.now(timezone.utc)
        except Exception as exc:
            oembed_erro = str(exc)[:1500]
            logger.exception("[@%s] falha no oEmbed do post %s: %s", conta.usuario, post_id, exc)

        sql = """
            insert into public.posts_x (
                conta_id,
                post_id,
                url,
                texto,
                publicado_em,
                coletado_em,
                metadados,
                metricas,
                midia,
                embed_html,
                embed_status,
                embed_atualizado_em,
                ativo
            )
            values (
                %s::uuid, %s, %s, %s, %s, now(), %s, %s, %s, %s, %s, %s, true
            )
            on conflict (post_id) do update set
                conta_id = excluded.conta_id,
                url = excluded.url,
                texto = excluded.texto,
                publicado_em = excluded.publicado_em,
                metadados = excluded.metadados,
                metricas = excluded.metricas,
                midia = excluded.midia,
                embed_html = coalesce(excluded.embed_html, public.posts_x.embed_html),
                embed_status = case
                    when excluded.embed_html is not null then 'ok'
                    else excluded.embed_status
                end,
                embed_atualizado_em = coalesce(
                    excluded.embed_atualizado_em,
                    public.posts_x.embed_atualizado_em
                ),
                ativo = true
            returning (xmax = 0) as inserido
        """

        midias = self._midias_do_post(post, media_por_chave)
        publicado_em = post.get("created_at")
        if publicado_em:
            publicado_em = datetime.fromisoformat(publicado_em.replace("Z", "+00:00"))

        metadados = {"origem": "x_api_v2"}
        if oembed_erro:
            metadados["oembed_erro"] = oembed_erro

        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        conta.id,
                        post_id,
                        url,
                        post.get("text"),
                        publicado_em,
                        Jsonb(metadados),
                        Jsonb(post.get("public_metrics") or {}),
                        Jsonb(midias),
                        embed_html,
                        embed_status,
                        embed_atualizado_em,
                    ),
                )
                inserido = bool(cur.fetchone()[0])
            conn.commit()

        logger.info(
            "[@%s] Supabase upsert post=%s inserido=%s embed=%s",
            conta.usuario,
            post_id,
            inserido,
            embed_status,
        )
        return inserido, embed_html is not None

    def _reparar_embeds_recentes(self, conta: ContaSync, limite: int = 3) -> int:
        sql = """
            select id, post_id, url
            from public.posts_x
            where conta_id = %s::uuid
              and ativo = true
              and (embed_html is null or embed_status <> 'ok')
            order by coalesce(publicado_em, coletado_em) desc
            limit %s
        """
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (conta.id, limite))
                pendentes = cur.fetchall()

        if pendentes:
            logger.info("[@%s] tentando reparar %s embed(s) pendente(s)", conta.usuario, len(pendentes))

        atualizados = 0
        for post_pk, post_id, url in pendentes:
            try:
                html = self._oembed(url)
            except Exception as exc:
                logger.exception("[@%s] reparo oEmbed falhou para post %s: %s", conta.usuario, post_id, exc)
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            update public.posts_x
                               set embed_status = 'erro',
                                   metadados = coalesce(metadados, '{}'::jsonb) || jsonb_build_object('oembed_erro', %s)
                             where id = %s
                            """,
                            (str(exc)[:1500], post_pk),
                        )
                    conn.commit()
                continue

            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        update public.posts_x
                           set embed_html = %s,
                               embed_status = 'ok',
                               embed_atualizado_em = now(),
                               metadados = coalesce(metadados, '{}'::jsonb) - 'oembed_erro'
                         where id = %s
                        """,
                        (html, post_pk),
                    )
                conn.commit()
            atualizados += 1
            logger.info("[@%s] embed reparado para post %s", conta.usuario, post_id)

        return atualizados

    def _finalizar_conta(
        self,
        conta: ContaSync,
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

    def sincronizar_conta(self, conta: ContaSync) -> dict:
        novos = 0
        embeds_atualizados = 0
        logger.info("[@%s] início da sincronização", conta.usuario)
        try:
            conta = self._resolver_usuario(conta)
            posts, media_por_chave = self._buscar_posts_novos(conta)

            for post in sorted(posts, key=lambda item: int(item["id"])):
                inserido, embed_ok = self._upsert_post(conta, post, media_por_chave)
                novos += int(inserido)
                embeds_atualizados += int(embed_ok)

            embeds_atualizados += self._reparar_embeds_recentes(conta)

            ids = [str(post["id"]) for post in posts]
            ultimo = max(ids, key=int) if ids else conta.ultimo_post_id
            self._finalizar_conta(conta, "ok", None, ultimo)

            logger.info(
                "[@%s] fim: novos=%s embeds=%s status=ok",
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
            logger.exception("[@%s] sincronização falhou: %s", conta.usuario, exc)
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

        logger.info("[job] início da sincronização do X: contas=%s", len(contas))
        resultados = [self.sincronizar_conta(conta) for conta in contas]

        resumo = {
            "contas": len(resultados),
            "novos": sum(item["novos"] for item in resultados),
            "embeds_atualizados": sum(item["embeds_atualizados"] for item in resultados),
            "resultados": resultados,
        }
        logger.info(
            "[job] fim: contas=%s novos=%s embeds=%s erros=%s",
            resumo["contas"],
            resumo["novos"],
            resumo["embeds_atualizados"],
            sum(1 for item in resultados if item["status"] != "ok"),
        )
        return resumo
