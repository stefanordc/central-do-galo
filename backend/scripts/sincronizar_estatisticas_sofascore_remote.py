from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import requests

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.data_collector_store import remote_call
from app.services.jogo_service import _sofascore_get, fechar_cliente_sofascore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("central_galo.dados.remote")

FOTMOB_TEAM_ID = 10272
FOTMOB_TEAM_URL = (
    "https://www.fotmob.com/api/data/teams"
    f"?id={FOTMOB_TEAM_ID}&ccode3=BRA"
)
FOTMOB_MATCH_URL = "https://www.fotmob.com/api/data/matchDetails?matchId={match_id}"
FOTMOB_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.fotmob.com/",
}


def _norm(value: object) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text)


def _fotmob_get(url: str) -> dict:
    response = requests.get(url, headers=FOTMOB_HEADERS, timeout=45)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"FotMob respondeu formato inesperado em {url}")
    return data


def _collect_matches(obj: object, out: list[dict]) -> None:
    if isinstance(obj, dict):
        if (
            obj.get("id") is not None
            and isinstance(obj.get("home"), dict)
            and isinstance(obj.get("away"), dict)
            and isinstance(obj.get("status"), dict)
        ):
            out.append(obj)
        for value in obj.values():
            _collect_matches(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _collect_matches(value, out)


def _parse_iso(value: object) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _rival_fotmob(match: dict) -> str:
    home = match.get("home") or {}
    away = match.get("away") or {}
    if int(home.get("id") or 0) == FOTMOB_TEAM_ID:
        return str(away.get("name") or "")
    return str(home.get("name") or "")


def _rival_banco(jogo: dict) -> str:
    lado = str(jogo.get("lado_galo") or "")
    return str(jogo.get("visitante") if lado == "home" else jogo.get("mandante") or "")


def _same_team(a: object, b: object) -> bool:
    aa = _norm(a)
    bb = _norm(b)
    if not aa or not bb:
        return False
    if aa == bb or aa in bb or bb in aa:
        return True
    aliases = {
        "athletico": "athletico paranaense",
        "atletico pr": "athletico paranaense",
        "atletico paranaense": "athletico paranaense",
        "atletico mg": "atletico mineiro",
        "atletico mineiro": "atletico mineiro",
    }
    return aliases.get(aa, aa) == aliases.get(bb, bb)


def _find_fotmob_match(jogo: dict, matches: list[dict]) -> dict | None:
    alvo = _parse_iso(jogo.get("inicio_em"))
    rival = _rival_banco(jogo)
    candidatos: list[tuple[float, dict]] = []

    for match in matches:
        status = match.get("status") or {}
        if not bool(status.get("finished")):
            continue

        ids = {
            int((match.get("home") or {}).get("id") or 0),
            int((match.get("away") or {}).get("id") or 0),
        }
        if FOTMOB_TEAM_ID not in ids:
            continue

        if not _same_team(rival, _rival_fotmob(match)):
            continue

        data = _parse_iso(status.get("utcTime"))
        if alvo is None or data is None:
            distancia = 0.0
        else:
            distancia = abs((data - alvo).total_seconds())

        # Cobertura suficiente para diferenças de timezone/horário cadastrado.
        if distancia <= 36 * 3600:
            candidatos.append((distancia, match))

    if not candidatos:
        return None

    candidatos.sort(key=lambda item: item[0])
    return candidatos[0][1]


def _stat_value(player: dict, key: str) -> tuple[object | None, object | None]:
    for group in player.get("stats") or []:
        stats = group.get("stats") or {}
        for item in stats.values():
            if not isinstance(item, dict):
                continue
            if str(item.get("key") or "") != key:
                continue
            stat = item.get("stat") or {}
            return stat.get("value"), stat.get("total")
    return None, None


def _position(usual: object, is_goalkeeper: bool) -> str | None:
    if is_goalkeeper:
        return "G"
    try:
        value = int(usual)
    except Exception:
        return None
    return {0: "G", 1: "D", 2: "M", 3: "F"}.get(value)


def _fotmob_lineups(detail: dict) -> dict:
    content = detail.get("content") or {}
    lineup = content.get("lineup") or {}
    player_stats = content.get("playerStats") or {}

    home_team = lineup.get("homeTeam") or {}
    away_team = lineup.get("awayTeam") or {}
    galo_lineup = home_team if int(home_team.get("id") or 0) == FOTMOB_TEAM_ID else away_team

    starters = {
        int(player.get("id"))
        for player in (galo_lineup.get("starters") or [])
        if player.get("id") is not None
    }

    players: list[dict] = []

    for raw in player_stats.values():
        if not isinstance(raw, dict):
            continue
        if int(raw.get("teamId") or 0) != FOTMOB_TEAM_ID:
            continue

        player_id = int(raw.get("id") or 0)
        if not player_id:
            continue

        minutes, _ = _stat_value(raw, "minutes_played")
        # Jogador relacionado, mas sem participação na partida.
        if minutes is None:
            continue

        rating, _ = _stat_value(raw, "rating_title")
        goals, _ = _stat_value(raw, "goals")
        assists, _ = _stat_value(raw, "assists")
        total_shots, _ = _stat_value(raw, "total_shots")
        shots_on, _ = _stat_value(raw, "ShotsOnTarget")
        shots_off, _ = _stat_value(raw, "ShotsOffTarget")
        accurate_pass, total_pass = _stat_value(raw, "accurate_passes")
        chances, _ = _stat_value(raw, "chances_created")
        tackles, _ = _stat_value(raw, "matchstats.headers.tackles")
        blocks, _ = _stat_value(raw, "shot_blocks")
        interceptions, _ = _stat_value(raw, "interceptions")
        duel_won, _ = _stat_value(raw, "duel_won")
        duel_lost, _ = _stat_value(raw, "duel_lost")
        dribble_won, dribble_total = _stat_value(raw, "dribbles_succeeded")
        fouls, _ = _stat_value(raw, "fouls")
        was_fouled, _ = _stat_value(raw, "was_fouled")
        saves, _ = _stat_value(raw, "saves")

        stats = {
            "minutesPlayed": minutes,
            "rating": rating,
            "goals": goals,
            "goalAssist": assists,
            "totalShots": total_shots,
            "onTargetScoringAttempt": shots_on,
            "shotOffTarget": shots_off,
            "totalPass": total_pass,
            "accuratePass": accurate_pass,
            "keyPass": chances,
            "totalTackle": tackles,
            "outfielderBlock": blocks,
            "interceptionWon": interceptions,
            "duelWon": duel_won,
            "duelLost": duel_lost,
            "totalContest": dribble_total,
            "wonContest": dribble_won,
            "fouls": fouls,
            "wasFouled": was_fouled,
            "saves": saves,
            "_source": "fotmob",
        }
        stats = {key: value for key, value in stats.items() if value is not None}

        players.append(
            {
                "player": {
                    "id": player_id,
                    "name": str(raw.get("name") or raw.get("shortName") or "Jogador"),
                    "shortName": str(raw.get("shortName") or raw.get("name") or "Jogador"),
                    "position": _position(raw.get("usualPosition"), bool(raw.get("isGoalkeeper"))),
                },
                "shirtNumber": raw.get("shirtNumber"),
                "substitute": player_id not in starters,
                "statistics": stats,
            }
        )

    lado = "home" if int(home_team.get("id") or 0) == FOTMOB_TEAM_ID else "away"
    return {lado: {"players": players}}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sincroniza estatísticas coletivas via SofaScore e individuais via FotMob."
    )
    parser.add_argument("--ano", type=int, default=datetime.now().year)
    parser.add_argument("--recent-days", type=int, default=4)
    args = parser.parse_args()

    jogos_resp = remote_call(
        "list_games",
        temporada=args.ano,
        recent_days=args.recent_days,
    )
    jogos = jogos_resp.get("data") or []

    logger.info("[Dados] %s jogo(s) pendente(s)/recente(s)", len(jogos))

    team_data = _fotmob_get(FOTMOB_TEAM_URL)
    fotmob_matches: list[dict] = []
    _collect_matches(team_data, fotmob_matches)

    # O mesmo jogo pode aparecer em mais de uma seção do payload do time.
    unique_matches: dict[int, dict] = {}
    for match in fotmob_matches:
        try:
            unique_matches[int(match["id"])] = match
        except Exception:
            pass
    fotmob_matches = list(unique_matches.values())

    logger.info("[Dados] FotMob carregou %s partida(s) únicas do Atlético", len(fotmob_matches))

    processados = 0
    jogadores_salvos = 0
    erros: list[str] = []

    try:
        for idx, jogo in enumerate(jogos, 1):
            event_id = int(jogo["event_id"])
            lado = str(jogo["lado_galo"])
            logger.info(
                "[Dados] %s/%s event=%s %s x %s",
                idx,
                len(jogos),
                event_id,
                jogo.get("mandante"),
                jogo.get("visitante"),
            )

            try:
                estatisticas = _sofascore_get(f"/event/{event_id}/statistics")

                fotmob_match = _find_fotmob_match(jogo, fotmob_matches)
                if fotmob_match is None:
                    raise RuntimeError(
                        "Partida correspondente não encontrada no FotMob: "
                        f"{jogo.get('mandante')} x {jogo.get('visitante')}"
                    )

                match_id = int(fotmob_match["id"])
                detail = _fotmob_get(FOTMOB_MATCH_URL.format(match_id=match_id))
                lineups = _fotmob_lineups(detail)

                qtd = len((lineups.get(lado) or {}).get("players") or [])
                logger.info(
                    "[Dados] FotMob match=%s jogadores_galo=%s",
                    match_id,
                    qtd,
                )
                if qtd == 0:
                    raise RuntimeError(
                        f"FotMob não retornou estatísticas individuais para match={match_id}"
                    )

                result = remote_call(
                    "save_game",
                    jogo_id=str(jogo["id"]),
                    event_id=event_id,
                    lado_galo=lado,
                    estatisticas=estatisticas,
                    lineups=lineups,
                )

                processados += 1
                jogadores_salvos += int(result.get("jogadores_salvos") or 0)
            except Exception as exc:
                logger.exception("[Dados] erro event=%s", event_id)
                erros.append(f"{event_id}: {exc}")

        status = remote_call("status", temporada=args.ano)

        saida = {
            "ano": args.ano,
            "processados": processados,
            "jogadores_salvos": jogadores_salvos,
            "erros": erros,
            "status": status,
        }
        print(json.dumps(saida, ensure_ascii=False, indent=2, default=str))

        if erros:
            raise SystemExit(1)
    finally:
        fechar_cliente_sofascore()


if __name__ == "__main__":
    main()
