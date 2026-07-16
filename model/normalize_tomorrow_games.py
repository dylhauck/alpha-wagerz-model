from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_hitter(
    hitter: dict[str, Any],
    team: str,
) -> dict[str, Any]:
    normalized = dict(hitter)

    player_name = (
        clean_text(normalized.get("Player"))
        or clean_text(normalized.get("name"))
        or clean_text(normalized.get("player_name"))
    )

    player_id = (
        normalized.get("Player ID")
        or normalized.get("player_id")
        or normalized.get("id")
    )

    normalized["Player"] = player_name
    normalized["name"] = player_name
    normalized["player_name"] = player_name

    normalized["Player ID"] = player_id
    normalized["player_id"] = player_id
    normalized["id"] = player_id

    normalized["Team"] = (
        clean_text(normalized.get("Team"))
        or clean_text(normalized.get("team"))
        or team
    )

    normalized["team"] = normalized["Team"]

    return normalized


def build_pitcher_object(
    name: str,
    pitcher_id: Any,
    team: str,
    opponent: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pitcher = dict(existing or {})

    pitcher_name = (
        clean_text(pitcher.get("Pitcher"))
        or clean_text(pitcher.get("name"))
        or clean_text(pitcher.get("player_name"))
        or clean_text(name)
    )

    resolved_id = (
        pitcher.get("Pitcher ID")
        or pitcher.get("pitcher_id")
        or pitcher.get("player_id")
        or pitcher.get("id")
        or pitcher_id
    )

    pitcher["Pitcher"] = pitcher_name
    pitcher["name"] = pitcher_name
    pitcher["player_name"] = pitcher_name

    pitcher["Pitcher ID"] = resolved_id
    pitcher["pitcher_id"] = resolved_id
    pitcher["player_id"] = resolved_id
    pitcher["id"] = resolved_id

    pitcher["Team"] = (
        clean_text(pitcher.get("Team"))
        or clean_text(pitcher.get("team"))
        or team
    )

    pitcher["team"] = pitcher["Team"]

    pitcher["Opponent"] = (
        clean_text(pitcher.get("Opponent"))
        or opponent
    )

    return pitcher


def normalize_tomorrow_games() -> int:
    updated = 0

    for game_file in GAMES_DIR.glob("*.json"):
        game = load_json(
            game_file,
            default={},
        )

        if not isinstance(game, dict) or not game:
            continue

        away_team = clean_text(
            game.get("away_team")
        )

        home_team = clean_text(
            game.get("home_team")
        )

        hitters_object = game.get("hitters")

        if not isinstance(hitters_object, dict):
            hitters_object = {}

        away_hitters = hitters_object.get("away")

        if not isinstance(away_hitters, list) or not away_hitters:
            away_hitters = game.get(
                "away_hitters",
                [],
            )

        home_hitters = hitters_object.get("home")

        if not isinstance(home_hitters, list) or not home_hitters:
            home_hitters = game.get(
                "home_hitters",
                [],
            )

        if not isinstance(away_hitters, list):
            away_hitters = []

        if not isinstance(home_hitters, list):
            home_hitters = []

        away_hitters = [
            normalize_hitter(
                hitter,
                away_team,
            )
            for hitter in away_hitters
            if isinstance(hitter, dict)
        ]

        home_hitters = [
            normalize_hitter(
                hitter,
                home_team,
            )
            for hitter in home_hitters
            if isinstance(hitter, dict)
        ]

        game["away_hitters"] = away_hitters
        game["home_hitters"] = home_hitters

        game["hitters"] = {
            "away": away_hitters,
            "home": home_hitters,
        }

        existing_pitchers = game.get(
            "pitchers",
            [],
        )

        if not isinstance(existing_pitchers, list):
            existing_pitchers = []

        away_existing = (
            existing_pitchers[0]
            if len(existing_pitchers) > 0
            and isinstance(existing_pitchers[0], dict)
            else game.get("away_pitcher")
        )

        home_existing = (
            existing_pitchers[1]
            if len(existing_pitchers) > 1
            and isinstance(existing_pitchers[1], dict)
            else game.get("home_pitcher")
        )

        if not isinstance(away_existing, dict):
            away_existing = {}

        if not isinstance(home_existing, dict):
            home_existing = {}

        away_pitcher = build_pitcher_object(
            name=clean_text(game.get("away_sp")),
            pitcher_id=game.get("away_sp_id"),
            team=away_team,
            opponent=home_team,
            existing=away_existing,
        )

        home_pitcher = build_pitcher_object(
            name=clean_text(game.get("home_sp")),
            pitcher_id=game.get("home_sp_id"),
            team=home_team,
            opponent=away_team,
            existing=home_existing,
        )

        game["away_pitcher"] = away_pitcher
        game["home_pitcher"] = home_pitcher

        game["pitchers"] = [
            away_pitcher,
            home_pitcher,
        ]

        save_json(
            game,
            game_file,
        )

        updated += 1

        print(
            f"✅ Normalized {game.get('game', game_file.name)} | "
            f"{len(away_hitters)} away hitters | "
            f"{len(home_hitters)} home hitters | "
            f"{away_pitcher.get('Pitcher') or 'TBD'} vs "
            f"{home_pitcher.get('Pitcher') or 'TBD'}"
        )

    print()
    print(
        f"✅ Normalized {updated} tomorrow game files"
    )

    return updated


if __name__ == "__main__":
    normalize_tomorrow_games()