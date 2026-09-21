from __future__ import annotations

import base64
import json
import os
import time
from urllib.parse import quote

import httpx

_REMOTE_URL = (os.getenv("YOUTUBE_REMOTE_STORE_URL") or "").strip()
_REMOTE_TOKEN = (os.getenv("YOUTUBE_REMOTE_STORE_TOKEN") or "").strip()
_OIDC_AUDIENCE = "central-do-galo-youtube"

_cached_oidc_token: str | None = None
_cached_oidc_exp: int = 0


def remote_enabled() -> bool:
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


def _github_oidc_token(*, force_refresh: bool = False) -> str:
    global _cached_oidc_token, _cached_oidc_exp

    now = int(time.time())
    if not force_refresh and _cached_oidc_token and _cached_oidc_exp > now + 60:
        return _cached_oidc_token

    if _REMOTE_TOKEN:
        _cached_oidc_token = _REMOTE_TOKEN
        _cached_oidc_exp = _jwt_exp(_REMOTE_TOKEN)
        return _REMOTE_TOKEN

    request_url = (os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL") or "").strip()
    request_token = (os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN") or "").strip()

    if not request_url or not request_token:
        raise RuntimeError(
            "YOUTUBE_REMOTE_STORE_URL está definido, mas o token OIDC do GitHub Actions não está disponível."
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


def remote_call(action: str, **payload):
    global _cached_oidc_token, _cached_oidc_exp

    if not _REMOTE_URL:
        raise RuntimeError("YOUTUBE_REMOTE_STORE_URL não configurada.")

    ultimo_erro: Exception | None = None

    for tentativa in range(1, 5):
        token = _github_oidc_token(force_refresh=tentativa > 1)

        try:
            timeout = httpx.Timeout(
                connect=20.0,
                read=90.0,
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

                if response.status_code >= 400:
                    try:
                        error_payload = response.json()
                        detail = (
                            error_payload.get("detail")
                            if isinstance(error_payload, dict)
                            else None
                        )
                    except (ValueError, json.JSONDecodeError):
                        detail = None

                    detail_text = (
                        str(detail).strip()
                        if detail
                        else response.text.strip()
                    )
                    mensagem = f"HTTP {response.status_code}"
                    if detail_text:
                        mensagem += f": {detail_text[:1000]}"

                    if response.status_code == 401 and not _REMOTE_TOKEN:
                        _cached_oidc_token = None
                        _cached_oidc_exp = 0
                        raise httpx.HTTPStatusError(
                            mensagem,
                            request=response.request,
                            response=response,
                        )

                    if (
                        response.status_code == 429
                        or response.status_code >= 500
                    ):
                        raise httpx.HTTPStatusError(
                            mensagem,
                            request=response.request,
                            response=response,
                        )

                    raise RuntimeError(mensagem)

                return response.json()

        except (
            httpx.ConnectError,
            httpx.ReadTimeout,
            httpx.ConnectTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError,
        ) as exc:
            ultimo_erro = exc

            if tentativa >= 4:
                raise

            # Backoff curto para absorver reset de conexão/TLS, 429 e 5xx
            # sem transformar uma falha transitória em falha do canal inteiro.
            time.sleep(min(10.0, 1.0 * (2 ** (tentativa - 1))))

    if ultimo_erro is not None:
        raise ultimo_erro

    raise RuntimeError(f"Falha remota inesperada na ação {action}.")
