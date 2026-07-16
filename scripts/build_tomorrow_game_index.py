import json
from pathlib import Path


GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)

OUTPUT_FILE = Path(
    "data/tomorrow/processed/game_index.json"
)


def load_json(filepath: Path):
    with filepath.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_json(data, filepath: Path):
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
        )


def build_tomorrow_game_index():
    games = []

    if not GAMES_DIR.exists():
        raise FileNotFoundError(
            f"Tomorrow games directory was not found: "
            f"{GAMES_DIR}"
        )

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)

        games.append(
            {
                "game_id": game["game_id"],
                "date": game["date"],
                "game": game["game"],
                "away_team": game["away_team"],
                "home_team": game["home_team"],
                "away_sp": game.get(
                    "away_sp",
                    "",
                ),
                "home_sp": game.get(
                    "home_sp",
                    "",
                ),
                "venue": game.get(
                    "venue",
                    "",
                ),
                "status": game.get(
                    "status",
                    "",
                ),
                "game_date_utc": game.get(
                    "game_date_utc",
                    "",
                ),
                "game_time": game.get(
                    "game_time",
                    "",
                ),
                "game_time_sort": game.get(
                    "game_time_sort",
                    "",
                ),
                "file": str(file).replace(
                    "\\",
                    "/",
                ),
            }
        )

    games.sort(
        key=lambda game: (
            game.get("game_time_sort", ""),
            game.get("game", ""),
        )
    )

    save_json(
        games,
        OUTPUT_FILE,
    )

    print(
        f"✅ Created tomorrow game index "
        f"with {len(games)} games"
    )
    print(f"📁 {OUTPUT_FILE}")


if __name__ == "__main__":
    build_tomorrow_game_index()