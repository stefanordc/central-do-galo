from __future__ import annotations

import base64
import json
import os
import time
from urllib.parse import quote

import httpx

_REMOTE_URL = (os.getenv("DATA_REMOTE_STORE_URL") or "").strip()
_REMOTE_TOKEN = (os.getenv("DATA_REMOTE_STORE_TOKEN") or "").strip()
_OIDC_AUDIENCE = "central-do-galo-dados"

_cached_oidc_token: str | None = None
_cached_oidc_exp: int = 0


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
            "DATA_REMOTE_STORE_URL está definido, mas o token OIDC do GitHub Actions não está disponível."
        )

    separator = "&" if "?" in request_url else "?"
    token_url = f"{request_url}{separator}audience={quote(_OIDC_AUDIENCE, safe='')}"

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
    if not _REMOTE_URL:
        raise RuntimeError("DATA_REMOTE_STORE_URL não configurada.")

    token = _github_oidc_token()

    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
        response = client.post(
            _REMOTE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"action": action, **payload},
        )
        response.raise_for_status()
        return response.json()
