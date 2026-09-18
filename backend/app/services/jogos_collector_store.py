from __future__ import annotations

import base64
import json
import os
import time
from urllib.parse import quote

import httpx

_REMOTE_URL = (os.getenv("JOGOS_REMOTE_STORE_URL") or "").strip()
_AUDIENCE = "central-do-galo-jogos"

_cached_token: str | None = None
_cached_exp: int = 0


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
    global _cached_token, _cached_exp

    now = int(time.time())
    if _cached_token and _cached_exp > now + 60:
        return _cached_token

    request_url = (os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL") or "").strip()
    request_token = (os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN") or "").strip()

    if not request_url or not request_token:
        raise RuntimeError("Token OIDC do GitHub Actions não está disponível.")

    separator = "&" if "?" in request_url else "?"
    token_url = f"{request_url}{separator}audience={quote(_AUDIENCE, safe='')}"

    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        response = client.get(
            token_url,
            headers={"Authorization": f"Bearer {request_token}"},
        )
        response.raise_for_status()
        token = str(response.json()["value"])

    _cached_token = token
    _cached_exp = _jwt_exp(token)
    return token


def remote_call(action: str, **payload):
    if not _REMOTE_URL:
        raise RuntimeError("JOGOS_REMOTE_STORE_URL não configurada.")

    token = _github_oidc_token()

    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
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
