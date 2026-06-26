from pathlib import Path

from utils.json_utils import load_json, save_json

GAMES_DIR = Path("data/processed/games")
OUTPUT_FILE = Path("data/processed/all_games.json")


def build_all_games():
    games = []

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})

        if game:
            games.append(game)

    games.sort(key=lambda g: g.get("game", ""))

    save_json(games, OUTPUT_FILE)

    print(f"✅ Built all-games payload with {len(games)} games")
    print(f"📁 {OUTPUT_FILE}")

    return games


if __name__ == "__main__":
    build_all_games()