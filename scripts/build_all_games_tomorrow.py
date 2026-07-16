from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SLATE_FILE = Path("data/tomorrow/raw/slate.json")
OUTPUT_FILE = Path("data/tomorrow/all_games.json")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def build_tomorrow_all_games() -> list[dict[str, Any]]:
    if not SLATE_FILE.exists():
        raise FileNotFoundError(
            f"Tomorrow slate file was not found: {SLATE_FILE}"
        )

    slate = load_json(SLATE_FILE)

    if not isinstance(slate, list):
        raise ValueError(
            f"Expected a list in {SLATE_FILE}, "
            f"but received {type(slate).__name__}."
        )

    all_games: list[dict[str, Any]] = []

    for raw_game in slate:
        if not isinstance(raw_game, dict):
            continue

        game_id = str(raw_game.get("game_id") or "").strip()

        if not game_id:
            continue

        away_team = str(
            raw_game.get("away_team") or ""
        ).strip()

        home_team = str(
            raw_game.get("home_team") or ""
        ).strip()

        game_name = str(
            raw_game.get("game")
            or f"{away_team} @ {home_team}"
        ).strip()

        all_games.append(
            {
                "game_id": game_id,
                "date": raw_game.get("date", ""),
                "game": game_name,
                "away_team": away_team,
                "home_team": home_team,
                "away_team_id": raw_game.get("away_team_id"),
                "home_team_id": raw_game.get("home_team_id"),
                "away_sp": raw_game.get("away_sp", ""),
                "away_sp_id": raw_game.get("away_sp_id"),
                "home_sp": raw_game.get("home_sp", ""),
                "home_sp_id": raw_game.get("home_sp_id"),
                "venue": raw_game.get("venue", ""),
                "status": raw_game.get("status", ""),
                "game_date_utc": raw_game.get(
                    "game_date_utc",
                    "",
                ),
                "game_time": raw_game.get("game_time", ""),
                "game_time_sort": raw_game.get(
                    "game_time_sort",
                    "",
                ),

                # These stay empty until tomorrow's lineup,
                # metrics, weather, and projection steps fill them.
                "away_hitters": [],
                "home_hitters": [],
                "hitters": [],
                "pitchers": [],
                "away_pitcher": {},
                "home_pitcher": {},
                "weather": {},
                "market": {},
                "projection": {},
                "slate_summary": {
                    "top_hr_target": "",
                    "top_pitcher": "",
                    "alpha_game_rating": "",
                    "notes": "",
                },
            }
        )

    all_games.sort(
        key=lambda game: (
            game.get("game_time_sort", ""),
            game.get("game", ""),
        )
    )

    save_json(
        all_games,
        OUTPUT_FILE,
    )

    print(
        f"✅ Built tomorrow all_games.json "
        f"with {len(all_games)} game"
        f"{'' if len(all_games) == 1 else 's'}"
    )
    print(f"📁 {OUTPUT_FILE}")

    return all_games


if __name__ == "__main__":
    build_tomorrow_all_games()