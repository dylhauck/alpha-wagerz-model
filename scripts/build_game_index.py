import json
from pathlib import Path


GAMES_DIR = Path("data/processed/games")
OUTPUT_FILE = Path("data/processed/game_index.json")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def build_game_index():
    games = []

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)

        games.append({
            "game_id": game["game_id"],
            "date": game["date"],
            "game": game["game"],
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "away_sp": game["away_sp"],
            "home_sp": game["home_sp"],
            "venue": game["venue"],
            "status": game["status"],
            "file": str(file).replace("\\", "/"),
        })

    games.sort(key=lambda x: x["game"])

    save_json(games, OUTPUT_FILE)

    print(f"✅ Created game index with {len(games)} games")
    print(f"📁 {OUTPUT_FILE}")


if __name__ == "__main__":
    build_game_index()