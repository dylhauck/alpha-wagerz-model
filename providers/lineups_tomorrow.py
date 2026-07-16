from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

from utils.json_utils import save_json


GAME_INDEX_FILE = Path(
    "data/tomorrow/processed/game_index.json"
)

OUTPUT_FILE = Path(
    "data/tomorrow/lineups.json"
)

MLB_BASE_URL = "https://statsapi.mlb.com/api/v1"
REQUEST_TIMEOUT = 30
LOCAL_TIMEZONE = ZoneInfo("America/Chicago")


def load_json(
    filepath: Path,
    default: Any,
) -> Any:
    if not filepath.exists():
        return default

    with filepath.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_json(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = requests.get(
        f"{MLB_BASE_URL}/{endpoint.lstrip('/')}",
        params=params or {},
        timeout=REQUEST_TIMEOUT,
        headers={
            "Accept": "application/json",
            "User-Agent": "Alpha-Wagerz/1.0",
        },
    )

    response.raise_for_status()

    payload = response.json()

    return payload if isinstance(payload, dict) else {}


def tomorrow_date_string() -> str:
    tomorrow = (
        datetime.now(LOCAL_TIMEZONE).date()
        + timedelta(days=1)
    )

    return tomorrow.isoformat()


def clean_id(value: Any) -> str:
    return str(value or "").strip()


def get_game_index() -> list[dict[str, Any]]:
    games = load_json(
        GAME_INDEX_FILE,
        default=[],
    )

    if not isinstance(games, list):
        raise ValueError(
            f"Expected a list in {GAME_INDEX_FILE}"
        )

    return games


def get_tomorrow_schedule_lookup() -> dict[str, dict[str, Any]]:
    date_string = tomorrow_date_string()

    payload = get_json(
        "schedule",
        {
            "sportId": 1,
            "date": date_string,
            "hydrate": (
                "probablePitcher,"
                "team,"
                "linescore"
            ),
        },
    )

    lookup: dict[str, dict[str, Any]] = {}

    for date_row in payload.get("dates", []):
        for game in date_row.get("games", []):
            game_id = clean_id(
                game.get("gamePk")
            )

            if not game_id:
                continue

            teams = game.get("teams", {}) or {}
            away = teams.get("away", {}) or {}
            home = teams.get("home", {}) or {}

            away_team = away.get("team", {}) or {}
            home_team = home.get("team", {}) or {}

            away_pitcher = (
                away.get("probablePitcher", {})
                or {}
            )

            home_pitcher = (
                home.get("probablePitcher", {})
                or {}
            )

            lookup[game_id] = {
                "game_id": game_id,

                "away_team_id": away_team.get("id"),
                "away_team": away_team.get("name", ""),

                "home_team_id": home_team.get("id"),
                "home_team": home_team.get("name", ""),

                "away_sp_id": away_pitcher.get("id"),
                "away_sp": away_pitcher.get(
                    "fullName",
                    "",
                ),

                "home_sp_id": home_pitcher.get("id"),
                "home_sp": home_pitcher.get(
                    "fullName",
                    "",
                ),
            }

    return lookup


def format_hitter(
    roster_row: dict[str, Any],
    team_id: int,
    team_name: str,
) -> dict[str, Any]:
    person = roster_row.get("person", {}) or {}
    position = roster_row.get("position", {}) or {}

    player_id = person.get("id")
    player_name = person.get("fullName", "")

    return {
        "id": player_id,
        "player_id": player_id,
        "Player ID": player_id,

        "name": player_name,
        "Player": player_name,

        "team_id": team_id,
        "Team ID": team_id,

        "team": team_name,
        "Team": team_name,

        "position": position.get(
            "abbreviation",
            "",
        ),
        "Position": position.get(
            "abbreviation",
            "",
        ),

        "batting_order": "",
        "lineup_source": "active_roster",
    }


def get_active_roster_hitters(
    team_id: int,
    team_name: str,
) -> list[dict[str, Any]]:
    payload = get_json(
        f"teams/{team_id}/roster",
        {
            "rosterType": "active",
            "hydrate": "person",
        },
    )

    hitters: list[dict[str, Any]] = []

    pitcher_positions = {
        "P",
        "SP",
        "RP",
        "CL",
        "TWP",
    }

    for roster_row in payload.get("roster", []):
        position = (
            roster_row.get("position", {})
            or {}
        ).get("abbreviation", "")

        if position in pitcher_positions:
            continue

        hitter = format_hitter(
            roster_row,
            team_id,
            team_name,
        )

        if not hitter.get("player_id"):
            continue

        if not hitter.get("Player"):
            continue

        hitters.append(hitter)

    hitters.sort(
        key=lambda hitter: (
            hitter.get("Position", ""),
            hitter.get("Player", ""),
        )
    )

    return hitters


def get_confirmed_lineups(
    game_id: str,
    away_team_id: int,
    away_team_name: str,
    home_team_id: int,
    home_team_name: str,
) -> dict[str, list[dict[str, Any]]]:
    try:
        payload = get_json(
            f"game/{game_id}/boxscore"
        )
    except requests.RequestException:
        return {
            "away": [],
            "home": [],
        }

    teams = payload.get("teams", {}) or {}

    output: dict[str, list[dict[str, Any]]] = {
        "away": [],
        "home": [],
    }

    side_info = {
        "away": (
            away_team_id,
            away_team_name,
        ),
        "home": (
            home_team_id,
            home_team_name,
        ),
    }

    for side in ["away", "home"]:
        team_id, team_name = side_info[side]

        side_data = teams.get(side, {}) or {}
        players = side_data.get("players", {}) or {}

        lineup: list[dict[str, Any]] = []

        for player_row in players.values():
            batting_order = player_row.get(
                "battingOrder"
            )

            if not batting_order:
                continue

            person = player_row.get("person", {}) or {}
            position = (
                player_row.get("position", {})
                or {}
            )

            player_id = person.get("id")
            player_name = person.get(
                "fullName",
                "",
            )

            if not player_id or not player_name:
                continue

            try:
                batting_order_value = int(
                    batting_order
                )
            except (TypeError, ValueError):
                batting_order_value = 9999

            lineup.append(
                {
                    "id": player_id,
                    "player_id": player_id,
                    "Player ID": player_id,

                    "name": player_name,
                    "Player": player_name,

                    "team_id": team_id,
                    "Team ID": team_id,

                    "team": team_name,
                    "Team": team_name,

                    "position": position.get(
                        "abbreviation",
                        "",
                    ),
                    "Position": position.get(
                        "abbreviation",
                        "",
                    ),

                    "batting_order": batting_order_value,
                    "lineup_source": "confirmed",
                }
            )

        lineup.sort(
            key=lambda hitter: hitter.get(
                "batting_order",
                9999,
            )
        )

        output[side] = lineup

    return output


def build_tomorrow_lineups() -> list[dict[str, Any]]:
    indexed_games = get_game_index()
    schedule_lookup = (
        get_tomorrow_schedule_lookup()
    )

    results: list[dict[str, Any]] = []

    for indexed_game in indexed_games:
        game_id = clean_id(
            indexed_game.get("game_id")
        )

        if not game_id:
            continue

        schedule_game = schedule_lookup.get(
            game_id,
            {},
        )

        away_team_id = schedule_game.get(
            "away_team_id"
        )

        home_team_id = schedule_game.get(
            "home_team_id"
        )

        away_team = (
            schedule_game.get("away_team")
            or indexed_game.get("away_team")
            or ""
        )

        home_team = (
            schedule_game.get("home_team")
            or indexed_game.get("home_team")
            or ""
        )

        if not away_team_id or not home_team_id:
            print(
                f"⚠️ Missing team IDs for "
                f"{indexed_game.get('game', game_id)}"
            )

            continue

        confirmed = get_confirmed_lineups(
            game_id=game_id,
            away_team_id=int(away_team_id),
            away_team_name=away_team,
            home_team_id=int(home_team_id),
            home_team_name=home_team,
        )

        away_hitters = confirmed.get(
            "away",
            [],
        )

        home_hitters = confirmed.get(
            "home",
            [],
        )

        away_lineup_confirmed = bool(
            away_hitters
        )

        home_lineup_confirmed = bool(
            home_hitters
        )

        if not away_hitters:
            away_hitters = (
                get_active_roster_hitters(
                    int(away_team_id),
                    away_team,
                )
            )

        if not home_hitters:
            home_hitters = (
                get_active_roster_hitters(
                    int(home_team_id),
                    home_team,
                )
            )

        if (
            away_lineup_confirmed
            and home_lineup_confirmed
        ):
            lineup_status = "confirmed"
        elif (
            away_lineup_confirmed
            or home_lineup_confirmed
        ):
            lineup_status = "partial"
        else:
            lineup_status = "roster_fallback"

        row = {
            "game_id": game_id,
            "game": indexed_game.get(
                "game",
                "",
            ),

            "lineup_status": lineup_status,

            "away_lineup_status": (
                "confirmed"
                if away_lineup_confirmed
                else "roster_fallback"
            ),

            "home_lineup_status": (
                "confirmed"
                if home_lineup_confirmed
                else "roster_fallback"
            ),

            "away_team_id": away_team_id,
            "away_team": away_team,

            "home_team_id": home_team_id,
            "home_team": home_team,

            "away_sp_id": schedule_game.get(
                "away_sp_id"
            ),
            "away_sp": schedule_game.get(
                "away_sp",
                "",
            ),

            "home_sp_id": schedule_game.get(
                "home_sp_id"
            ),
            "home_sp": schedule_game.get(
                "home_sp",
                "",
            ),

            "away_hitters": away_hitters,
            "home_hitters": home_hitters,
        }

        results.append(row)

        print(
            f"✅ {row['game']} — "
            f"{lineup_status} | "
            f"{len(away_hitters)} away hitters | "
            f"{len(home_hitters)} home hitters | "
            f"SP: {row['away_sp'] or 'TBD'} vs "
            f"{row['home_sp'] or 'TBD'}"
        )

    save_json(
        results,
        OUTPUT_FILE,
    )

    print()
    print(
        f"✅ Saved tomorrow lineup data for "
        f"{len(results)} games"
    )
    print(f"📁 {OUTPUT_FILE}")

    return results


if __name__ == "__main__":
    build_tomorrow_lineups()