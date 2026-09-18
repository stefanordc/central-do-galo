from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.jogo_service import _sofascore_get, fechar_cliente_sofascore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("central_galo.dados.remoto")

REMOTE_URL = (
    os.getenv("DADOS_REMOTE_STORE_URL")
    or "https://lhrpsquyzehevxuogxar.supabase.co/functions/v1/dados-collector-store"
).strip()

REMOTE_TOKEN = (os.getenv("DADOS_REMOTE_STORE_TOKEN") or "").strip()
OIDC_AUDIENCE = "central-do-galo-dados"

_cached_token: str | None = None
_cached_exp = 0


def _jwt_exp(token: str) -> int:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        return int(json.loads(decoded.decode("utf-8")).get("exp", 0))
    except Exception:
        return 0


def _oidc_token() -> str:
    global _cached_token, _cached_exp

    now = int(time.time())
    if _cached_token and _cached_exp > now + 60:
        return _cached_token

    if REMOTE_TOKEN:
        _cached_token = REMOTE_TOKEN
        _cached_exp = _jwt_exp(REMOTE_TOKEN)
        return REMOTE_TOKEN

    request_url = (os.getenv("ACTIONS_ID_TOKEN_REQUEST_URL") or "").strip()
    request_token = (os.getenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN") or "").strip()

    if not request_url or not request_token:
        raise RuntimeError(
            "Token OIDC do GitHub Actions não está disponível."
        )

    separator = "&" if "?" in request_url else "?"
    token_url = (
        f"{request_url}{separator}audience={quote(OIDC_AUDIENCE, safe='')}"
    )

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


def _remote_call(action: str, **payload):
    token = _oidc_token()

    with httpx.Client(timeout=60.0, follow_redirects=True) as client:
        response = client.post(
            REMOTE_URL,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"action": action, **payload},
        )

        if response.status_code >= 400:
            detalhe = response.text[:1000]
            raise RuntimeError(
                f"Store remoto respondeu {response.status_code}: {detalhe}"
            )

        return response.json()


def _event_id(jogo: dict) -> int | None:
    value = jogo.get("event_id")
    try:
        if value is not None:
            return int(value)
    except (TypeError, ValueError):
        pass

    externo = str(jogo.get("id_externo") or "")
    if externo.startswith("sofascore:"):
        try:
            return int(externo.split(":", 1)[1])
        except (TypeError, ValueError):
            return None

    return None


def _lado_galo(jogo: dict) -> str:
    lado = str(jogo.get("lado_galo") or "").strip().lower()
    if lado in {"home", "away"}:
        return lado

    metadados = jogo.get("metadados") or {}
    team_ids = ((metadados.get("sofascore") or {}).get("team_ids") or {})

    if team_ids.get("home") == 1977:
        return "home"
    if team_ids.get("away") == 1977:
        return "away"

    mandante = str(jogo.get("mandante") or "").lower()
    return "home" if "atlético mineiro" in mandante or "atletico mineiro" in mandante else "away"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza estatísticas coletivas e individuais via SofaScore usando store remoto."
    )
    parser.add_argument("--ano", type=int, default=datetime.now().year)
    parser.add_argument("--forcar", action="store_true")
    parser.add_argument("--limite", type=int, default=None)
    args = parser.parse_args()

    logger.info("[Dados] consultando jogos pendentes de %s", args.ano)

    result = _remote_call(
        "pending_games",
        ano=args.ano,
        forcar=bool(args.forcar),
    )

    jogos = list(result.get("games") or [])
    if args.limite is not None:
        jogos = jogos[: max(0, int(args.limite))]

    logger.info(
        "[Dados] finalizados=%s pendentes=%s processar=%s",
        result.get("total_finalizados"),
        result.get("total"),
        len(jogos),
    )

    processados = 0
    erros: list[str] = []
    jogadores_utilizados = 0

    try:
        for indice, jogo in enumerate(jogos, 1):
            event_id = _event_id(jogo)
            if event_id is None:
                erros.append(f"{jogo.get('id')}: event_id ausente")
                continue

            lado = _lado_galo(jogo)
            logger.info(
                "[Dados] %s/%s evento=%s %s x %s",
                indice,
                len(jogos),
                event_id,
                jogo.get("mandante"),
                jogo.get("visitante"),
            )

            try:
                estatisticas = _sofascore_get(f"/event/{event_id}/statistics")
                lineups = _sofascore_get(f"/event/{event_id}/lineups")

                salvo = _remote_call(
                    "save_game_stats",
                    jogo_id=str(jogo["id"]),
                    event_id=event_id,
                    lado_galo=lado,
                    estatisticas=estatisticas,
                    lineups=lineups,
                )

                processados += 1
                jogadores_utilizados += int(
                    salvo.get("jogadores_utilizados") or 0
                )

                logger.info(
                    "[Dados] evento=%s salvo lineup=%s utilizados=%s",
                    event_id,
                    salvo.get("jogadores_lineup"),
                    salvo.get("jogadores_utilizados"),
                )
            except Exception as exc:
                logger.exception("[Dados] falha no evento %s", event_id)
                erros.append(f"{event_id}: {exc}")

        status = _remote_call("status", ano=args.ano)

        saida = {
            "ano": args.ano,
            "pendentes_encontrados": len(jogos),
            "processados": processados,
            "jogadores_utilizados": jogadores_utilizados,
            "erros": erros,
            "status": status,
        }

        print(json.dumps(saida, ensure_ascii=False, indent=2))
    finally:
        fechar_cliente_sofascore()

    if erros:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
