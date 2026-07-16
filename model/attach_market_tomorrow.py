from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


ALL_GAMES_FILE = Path("data/tomorrow/all_games.json")
MARKET_FILE = Path("data/tomorrow/market_lines.json")


def clean_id(value: Any) -> str:
    return str(value or "").strip()


def attach_tomorrow_market_to_games():
    if not ALL_GAMES_FILE.exists():
        raise FileNotFoundError(
            f"Tomorrow games file was not found: {ALL_GAMES_FILE}"
        )

    games = load_json(
        ALL_GAMES_FILE,
        default=[],
    )

    market_rows = load_json(
        MARKET_FILE,
        default=[],
    )

    if not isinstance(games, list):
        raise ValueError(
            f"Expected a list in {ALL_GAMES_FILE}"
        )

    if not isinstance(market_rows, list):
        raise ValueError(
            f"Expected a list in {MARKET_FILE}"
        )

    market_by_game_id = {
        clean_id(row.get("game_id")): row
        for row in market_rows
        if clean_id(row.get("game_id"))
    }

    attached = 0

    for game in games:
        game_id = clean_id(
            game.get("game_id")
        )

        market = market_by_game_id.get(
            game_id,
            {},
        )

        game["market"] = market

        if market:
            attached += 1

    save_json(
        games,
        ALL_GAMES_FILE,
    )

    print(
        f"✅ Attached tomorrow market data to "
        f"{attached} of {len(games)} games"
    )
    print(f"📁 {ALL_GAMES_FILE}")

    return games


if __name__ == "__main__":
    attach_tomorrow_market_to_games()