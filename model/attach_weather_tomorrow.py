from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


ALL_GAMES_FILE = Path(
    "data/tomorrow/all_games.json"
)

WEATHER_FILE = Path(
    "data/tomorrow/weather.json"
)


def clean_id(value: Any) -> str:
    return str(value or "").strip()


def attach_tomorrow_weather_to_games():
    if not ALL_GAMES_FILE.exists():
        raise FileNotFoundError(
            f"Tomorrow games file was not found: "
            f"{ALL_GAMES_FILE}"
        )

    games = load_json(
        ALL_GAMES_FILE,
        default=[],
    )

    weather_rows = load_json(
        WEATHER_FILE,
        default=[],
    )

    if not isinstance(games, list):
        raise ValueError(
            f"Expected a list in {ALL_GAMES_FILE}"
        )

    if not isinstance(weather_rows, list):
        raise ValueError(
            f"Expected a list in {WEATHER_FILE}"
        )

    weather_by_game_id = {
        clean_id(row.get("game_id")): row
        for row in weather_rows
        if clean_id(row.get("game_id"))
    }

    attached = 0

    for game in games:
        game_id = clean_id(
            game.get("game_id")
        )

        weather = weather_by_game_id.get(
            game_id,
            {},
        )

        game["weather"] = weather

        if weather:
            attached += 1

    save_json(
        games,
        ALL_GAMES_FILE,
    )

    print(
        f"✅ Attached tomorrow weather to "
        f"{attached} of {len(games)} games"
    )
    print(f"📁 {ALL_GAMES_FILE}")

    return games


if __name__ == "__main__":
    attach_tomorrow_weather_to_games()