from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def finalize_tomorrow_structure() -> int:
    updated = 0

    for game_file in GAMES_DIR.glob("*.json"):
        game = load_json(
            game_file,
            default={},
        )

        if not isinstance(game, dict) or not game:
            continue

        game_name = clean_text(
            game.get("game")
        )

        hitters = game.get("hitters")

        if not isinstance(hitters, dict):
            hitters = {
                "away": game.get(
                    "away_hitters",
                    [],
                ),
                "home": game.get(
                    "home_hitters",
                    [],
                ),
            }

        away_hitters = hitters.get(
            "away",
            [],
        )

        home_hitters = hitters.get(
            "home",
            [],
        )

        if not isinstance(away_hitters, list):
            away_hitters = []

        if not isinstance(home_hitters, list):
            home_hitters = []

        for hitter in away_hitters:
            if isinstance(hitter, dict):
                hitter["Game"] = (
                    hitter.get("Game")
                    or game_name
                )

        for hitter in home_hitters:
            if isinstance(hitter, dict):
                hitter["Game"] = (
                    hitter.get("Game")
                    or game_name
                )

        game["away_hitters"] = away_hitters
        game["home_hitters"] = home_hitters

        game["hitters"] = {
            "away": away_hitters,
            "home": home_hitters,
        }

        pitchers = game.get(
            "pitchers",
            [],
        )

        if not isinstance(pitchers, list):
            pitchers = []

        for pitcher in pitchers:
            if not isinstance(pitcher, dict):
                continue

            pitcher["Game"] = game_name
            pitcher["game"] = game_name
            pitcher["Matchup"] = game_name

        game["pitchers"] = pitchers

        game["away_pitcher"] = (
            pitchers[0]
            if len(pitchers) > 0
            else {}
        )

        game["home_pitcher"] = (
            pitchers[1]
            if len(pitchers) > 1
            else {}
        )

        save_json(
            game,
            game_file,
        )

        updated += 1

        print(
            f"✅ Finalized {game_name} | "
            f"{len(away_hitters)} away hitters | "
            f"{len(home_hitters)} home hitters | "
            f"{len(pitchers)} pitchers"
        )

    print()
    print(
        f"✅ Finalized {updated} tomorrow games"
    )

    return updated


if __name__ == "__main__":
    finalize_tomorrow_structure()