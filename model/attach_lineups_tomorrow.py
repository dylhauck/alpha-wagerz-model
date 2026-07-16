from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LINEUPS_FILE = Path(
    "data/tomorrow/lineups.json"
)

GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)


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


def save_json(
    data: Any,
    filepath: Path,
) -> None:
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


def attach_tomorrow_lineups_to_games() -> int:
    lineup_rows = load_json(
        LINEUPS_FILE,
        default=[],
    )

    if not isinstance(lineup_rows, list):
        raise ValueError(
            f"Expected a list in {LINEUPS_FILE}"
        )

    attached = 0

    for lineup in lineup_rows:
        game_id = str(
            lineup.get("game_id") or ""
        ).strip()

        if not game_id:
            continue

        game_file = (
            GAMES_DIR / f"{game_id}.json"
        )

        if not game_file.exists():
            print(
                f"⚠️ Missing tomorrow game file: "
                f"{game_file}"
            )
            continue

        game = load_json(
            game_file,
            default={},
        )

        if not isinstance(game, dict):
            continue

        away_hitters = lineup.get(
            "away_hitters",
            [],
        )

        home_hitters = lineup.get(
            "home_hitters",
            [],
        )

        game["lineup_status"] = lineup.get(
            "lineup_status",
            "roster_fallback",
        )

        game["away_lineup_status"] = (
            lineup.get(
                "away_lineup_status",
                "roster_fallback",
            )
        )

        game["home_lineup_status"] = (
            lineup.get(
                "home_lineup_status",
                "roster_fallback",
            )
        )

        game["away_team_id"] = lineup.get(
            "away_team_id"
        )

        game["home_team_id"] = lineup.get(
            "home_team_id"
        )

        game["away_sp"] = (
            lineup.get("away_sp")
            or game.get("away_sp")
            or ""
        )

        game["home_sp"] = (
            lineup.get("home_sp")
            or game.get("home_sp")
            or ""
        )

        game["away_sp_id"] = (
            lineup.get("away_sp_id")
            or game.get("away_sp_id")
        )

        game["home_sp_id"] = (
            lineup.get("home_sp_id")
            or game.get("home_sp_id")
        )

        game["away_pitcher_id"] = (
            game.get("away_sp_id")
        )

        game["home_pitcher_id"] = (
            game.get("home_sp_id")
        )

        game["away_hitters"] = (
            away_hitters
            if isinstance(away_hitters, list)
            else []
        )

        game["home_hitters"] = (
            home_hitters
            if isinstance(home_hitters, list)
            else []
        )

        game["hitters"] = {
            "away": game["away_hitters"],
            "home": game["home_hitters"],
        }

        save_json(
            game,
            game_file,
        )

        attached += 1

        print(
            f"✅ Attached {game.get('game', game_id)} | "
            f"{len(game['away_hitters'])} away hitters | "
            f"{len(game['home_hitters'])} home hitters | "
            f"{game.get('away_sp') or 'TBD'} vs "
            f"{game.get('home_sp') or 'TBD'}"
        )

    print()
    print(
        f"✅ Attached tomorrow rosters and "
        f"probable pitchers to {attached} games"
    )

    return attached


if __name__ == "__main__":
    attach_tomorrow_lineups_to_games()