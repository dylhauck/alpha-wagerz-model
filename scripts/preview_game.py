import json
from pathlib import Path


GAME_INDEX_FILE = Path("data/processed/game_index.json")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def preview_first_game():
    games = load_json(GAME_INDEX_FILE)

    selected = games[0]
    game_file = Path(selected["file"])
    game = load_json(game_file)

    print("\n==============================")
    print(f"Selected Game: {game['game']}")
    print("==============================")
    print(f"Venue: {game['venue']}")
    print(f"Away SP: {game['away_sp']}")
    print(f"Home SP: {game['home_sp']}")
    print(f"Status: {game['status']}")

    print("\nSlate Summary")
    print(game["slate_summary"])

    print("\nHitters")
    print(game["hitters"])

    print("\nPitchers")
    print(game["pitchers"])

    print("\nWeather")
    print(game["weather"])


if __name__ == "__main__":
    preview_first_game()