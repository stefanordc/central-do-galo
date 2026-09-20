from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from datetime import datetime
from typing import Iterable
from urllib.parse import quote
from uuid import UUID

import httpx

from app.collectors.models import ArticleMetadata
from app.services.news_classifier import classify_news
from app.services.news_classifier import save_news_categories as _local_save_news_categories
from app.services.news_service import (
    atualizar_imagem_noticia_por_url as _local_atualizar_imagem,
    obter_fonte_por_slug as _local_obter_fonte,
    salvar_noticia as _local_salvar_noticia,
    urls_ja_cadastradas as _local_urls_ja_cadastradas,
    urls_sem_imagem as _local_urls_sem_imagem,
)


_REMOTE_URL = (os.getenv("NEWS_REMOTE_STORE_URL") or "").strip()
_REMOTE_TOKEN = (os.getenv("NEWS_REMOTE_STORE_TOKEN") or "").strip()
_OIDC_AUDIENCE = "central-do-galo-news"

_cached_oidc_token: str | None = None
_cached_oidc_exp: int = 0


def _remote_enabled() -> bool:
    return bool(_REMOTE_URL)


def _jwt_exp(token: str) -> int:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        data = json.loads(decoded.decode("utf-8"))
        return int(data.get("exp", 0))
    except Exception:
        return 0


def _github_oidc_token() -> str:
    global _cached_oidc_token, _cached_oidc_exp

    now = int(time.time())
    if _cached_oidc_token and _cached_oidc_exp > now + 60:
        return _cached_oidc_token

    if _REMOTE_TOKEN:
        _cached_oidc_token = _REMOTE_TOKEN
        _cached_oidc_exp = _jwt_exp(_REMOTE_TOKEN)
        return _REMOTE_TOKEN

    request_url = (os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL") or "").strip()
    request_token = (os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN") or "").strip()

    if not request_url or not request_token:
        raise RuntimeError(
            "NEWS_REMOTE_STORE_URL está definido, mas o token OIDC do GitHub Actions não está disponível."
        )

    separator = "&" if "?" in request_url else "?"
    token_url = (
        f"{request_url}{separator}audience={quote(_OIDC_AUDIENCE, safe='')}"
    )

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        response = client.get(
            token_url,
            headers={"Authorization": f"Bearer {request_token}"},
        )
        response.raise_for_status()
        token = str(response.json()["value"])

    _cached_oidc_token = token
    _cached_oidc_exp = _jwt_exp(token)
    return token


def _remote_call(action: str, **payload):
    ultimo_erro: Exception | None = None

    for tentativa in range(1, 5):
        token = _github_oidc_token()

        try:
            timeout = httpx.Timeout(
                connect=20.0,
                read=120.0,
                write=30.0,
                pool=20.0,
            )

            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.post(
                    _REMOTE_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json={"action": action, **payload},
                )

                if response.status_code in {429, 502, 503, 504}:
                    raise httpx.HTTPStatusError(
                        f"Resposta temporária HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                response.raise_for_status()
                return response.json()
        except (
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError,
        ) as exc:
            ultimo_erro = exc
            if tentativa >= 4:
                raise

            time.sleep(min(12.0, 1.5 * (2 ** (tentativa - 1))))

    if ultimo_erro is not None:
        raise ultimo_erro

    raise RuntimeError(f"Falha remota inesperada na ação {action}.")


def obter_fonte_por_slug(slug: str) -> dict | None:
    if not _remote_enabled():
        return _local_obter_fonte(slug)

    result = _remote_call("get_source", slug=slug)
    return result.get("data")


def urls_ja_cadastradas(urls: Iterable[str]) -> set[str]:
    values = list(dict.fromkeys(urls))
    if not values:
        return set()

    if not _remote_enabled():
        return _local_urls_ja_cadastradas(values)

    existentes: set[str] = set()
    tamanho_lote = 100

    for inicio in range(0, len(values), tamanho_lote):
        lote = values[inicio : inicio + tamanho_lote]
        result = _remote_call("existing_urls", urls=lote)
        existentes.update(result.get("urls", []))

    return existentes


def urls_sem_imagem(urls: Iterable[str]) -> set[str]:
    values = list(dict.fromkeys(urls))
    if not values:
        return set()

    if not _remote_enabled():
        return _local_urls_sem_imagem(values)

    faltantes: set[str] = set()
    tamanho_lote = 100

    for inicio in range(0, len(values), tamanho_lote):
        lote = values[inicio : inicio + tamanho_lote]
        result = _remote_call("missing_images", urls=lote)
        faltantes.update(result.get("urls", []))

    return faltantes


def atualizar_imagem_noticia_por_url(
    url: str,
    imagem_url: str,
    *,
    sobrescrever: bool = False,
) -> bool:
    if not _remote_enabled():
        return _local_atualizar_imagem(
            url,
            imagem_url,
            sobrescrever=sobrescrever,
        )

    result = _remote_call(
        "update_image",
        url=url,
        imagem_url=imagem_url,
        sobrescrever=sobrescrever,
    )
    return bool(result.get("updated"))


def _hash_noticia(titulo: str, url: str) -> str:
    normalized = f"{titulo.strip().lower()}|{url.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _serialize_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def salvar_noticia(
    fonte_id: UUID | str,
    oficial: bool,
    article: ArticleMetadata,
) -> UUID | str:
    if not _remote_enabled():
        return _local_salvar_noticia(
            fonte_id=fonte_id,
            oficial=oficial,
            article=article,
        )

    result = _remote_call(
        "save_news",
        fonte_id=str(fonte_id),
        oficial=bool(oficial),
        hash_conteudo=_hash_noticia(article.titulo, article.url),
        article={
            "titulo": article.titulo,
            "url": article.url,
            "resumo": article.resumo,
            "imagem_url": article.imagem_url,
            "categoria": article.categoria,
            "publicado_em": _serialize_datetime(article.publicado_em),
            "metadados": article.metadados,
        },
    )

    # No modo remoto, a Edge Function/RPC já devolve o identificador da notícia.
    # Não reconvertemos com UUID() aqui: o valor só precisa ser serializado na
    # chamada seguinte (save_categories), e uma conversão extra fazia a coleta
    # falhar com "badly formed hexadecimal UUID string" em respostas válidas.
    noticia_id = result.get("id")
    if noticia_id is None or not str(noticia_id).strip():
        raise RuntimeError("save_news remoto não retornou o id da notícia")
    return str(noticia_id).strip()


def save_news_categories(
    noticia_id: UUID | str,
    titulo: str,
    resumo: str | None = None,
) -> None:
    if not _remote_enabled():
        _local_save_news_categories(
            noticia_id=noticia_id,
            titulo=titulo,
            resumo=resumo,
        )
        return

    matches = classify_news(titulo=titulo, resumo=resumo)
    _remote_call(
        "save_categories",
        noticia_id=str(noticia_id),
        matches=[
            {
                "slug": match.slug,
                "confidence": match.confidence,
            }
            for match in matches
        ],
    )
