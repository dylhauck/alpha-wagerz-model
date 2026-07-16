from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"

OUTPUT_FILE = Path("data/tomorrow/raw/slate.json")

CENTRAL_TIME = ZoneInfo("America/Chicago")
UTC_TIME = ZoneInfo("UTC")


def tomorrow_date() -> str:
    """
    Always determine the baseball slate date in Central Time,
    regardless of whether the script runs on Mac or Windows.
    """
    current_central_date = datetime.now(CENTRAL_TIME).date()
    return (current_central_date + timedelta(days=1)).isoformat()


def format_game_time(game_date_utc: str) -> tuple[str, str]:
    if not game_date_utc:
        return "", ""

    utc_datetime = datetime.fromisoformat(
        game_date_utc.replace("Z", "+00:00")
    )

    central_datetime = utc_datetime.astimezone(CENTRAL_TIME)

    display_time = central_datetime.strftime("%I:%M %p").lstrip("0")
    sort_time = central_datetime.strftime("%H:%M")

    return display_time, sort_time


def save_json(data: object, filepath: Path) -> None:
    filepath.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with filepath.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def get_tomorrows_slate() -> list[dict]:
    slate_date = tomorrow_date()

    params = {
        "sportId": 1,
        "startDate": slate_date,
        "endDate": slate_date,
        "gameTypes": "R",
        "hydrate": "probablePitcher,venue,team",
        "language": "en",
    }

    print(f"📅 Tomorrow slate date: {slate_date}")
    print(f"🌐 Requesting: {MLB_SCHEDULE_URL}")
    print(f"🔎 Parameters: {params}")

    response = requests.get(
        MLB_SCHEDULE_URL,
        params=params,
        headers={
            "Accept": "application/json",
            "User-Agent": "Alpha-Wagerz/1.0",
        },
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    print(
        "⚾ MLB response totalGames:",
        payload.get("totalGames", 0),
    )

    games: list[dict] = []

    for date_entry in payload.get("dates", []):
        official_date = (
            date_entry.get("date")
            or slate_date
        )

        for game in date_entry.get("games", []):
            teams = game.get("teams") or {}
            away_data = teams.get("away") or {}
            home_data = teams.get("home") or {}

            away_team_data = away_data.get("team") or {}
            home_team_data = home_data.get("team") or {}

            away_team = away_team_data.get("name", "")
            home_team = home_team_data.get("name", "")

            away_pitcher_data = (
                away_data.get("probablePitcher")
                or {}
            )

            home_pitcher_data = (
                home_data.get("probablePitcher")
                or {}
            )

            game_date_utc = game.get("gameDate", "")

            game_time, game_time_sort = format_game_time(
                game_date_utc
            )

            game_id = game.get("gamePk")

            if not game_id:
                continue

            games.append(
                {
                    "game_id": str(game_id),
                    "date": official_date,
                    "game": f"{away_team} @ {home_team}",
                    "away_team": away_team,
                    "home_team": home_team,
                    "away_team_id": away_team_data.get("id"),
                    "home_team_id": home_team_data.get("id"),
                    "away_sp": away_pitcher_data.get(
                        "fullName",
                        "",
                    ),
                    "away_sp_id": away_pitcher_data.get("id"),
                    "home_sp": home_pitcher_data.get(
                        "fullName",
                        "",
                    ),
                    "home_sp_id": home_pitcher_data.get("id"),
                    "venue": (
                        game.get("venue") or {}
                    ).get("name", ""),
                    "status": (
                        game.get("status") or {}
                    ).get("detailedState", ""),
                    "game_date_utc": game_date_utc,
                    "game_time": game_time,
                    "game_time_sort": game_time_sort,
                }
            )

    games.sort(
        key=lambda game: (
            game.get("game_time_sort", ""),
            game.get("game", ""),
        )
    )

    return games


def build_tomorrow_slate() -> list[dict]:
    games = get_tomorrows_slate()

    save_json(
        games,
        OUTPUT_FILE,
    )

    print(
        f"✅ Saved {len(games)} tomorrow game"
        f"{'' if len(games) == 1 else 's'}"
    )
    print(f"📁 {OUTPUT_FILE}")

    for game in games:
        print(
            f"   {game['game']} — "
            f"{game.get('game_time') or 'Time TBD'}"
        )

    return games


if __name__ == "__main__":
    build_tomorrow_slate()