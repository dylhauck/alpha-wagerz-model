import json
from pathlib import Path


RAW_SLATE_FILE = "data/raw/todays_slate.json"
OUTPUT_DIR = Path("data/processed/games")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def build_game_files():
    slate = load_json(RAW_SLATE_FILE)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for game in slate:
        game_id = str(game["game_id"])

        game_file = {
            "game_id": game_id,
            "date": game["date"],
            "game": game["game"],
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "away_sp": game["away_sp"],
            "home_sp": game["home_sp"],
            "venue": game["venue"],
            "status": game["status"],

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

        save_json(game_file, OUTPUT_DIR / f"{game_id}.json")

    print(f"✅ Created {len(slate)} game files in data/processed/games")


if __name__ == "__main__":
    build_game_files()