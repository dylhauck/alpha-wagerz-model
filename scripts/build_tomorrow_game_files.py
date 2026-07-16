import json
import shutil
from pathlib import Path


RAW_SLATE_FILE = Path(
    "data/tomorrow/raw/slate.json"
)

OUTPUT_DIR = Path(
    "data/tomorrow/processed/games"
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


def clear_tomorrow_games():
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("🗑️ Cleared previous tomorrow game files")


def build_tomorrow_game_files():
    if not RAW_SLATE_FILE.exists():
        raise FileNotFoundError(
            f"Tomorrow slate was not found: "
            f"{RAW_SLATE_FILE}"
        )

    slate = load_json(RAW_SLATE_FILE)

    clear_tomorrow_games()

    for game in slate:
        game_id = str(game["game_id"])

        game_file = {
            "game_id": game_id,
            "date": game["date"],
            "game": game["game"],
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "away_sp": game.get("away_sp", ""),
            "home_sp": game.get("home_sp", ""),
            "venue": game.get("venue", ""),
            "status": game.get("status", ""),
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
            "slate_summary": {
                "top_hr_target": "",
                "top_pitcher": "",
                "alpha_game_rating": "",
                "notes": "",
            },
            "hitters": [],
            "pitchers": [],
            "weather": {},
        }

        save_json(
            game_file,
            OUTPUT_DIR / f"{game_id}.json",
        )

    print(
        f"✅ Created {len(slate)} tomorrow game files"
    )
    print(f"📁 {OUTPUT_DIR}")


if __name__ == "__main__":
    build_tomorrow_game_files()