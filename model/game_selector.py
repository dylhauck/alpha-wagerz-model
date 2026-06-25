import json
from pathlib import Path


GAME_INDEX_FILE = Path("data/processed/game_index.json")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_game_index():
    return load_json(GAME_INDEX_FILE)


def get_game_by_id(game_id):
    games = get_game_index()

    match = next((game for game in games if str(game["game_id"]) == str(game_id)), None)

    if not match:
        raise ValueError(f"No game found for game_id: {game_id}")

    return load_json(match["file"])


def list_games():
    games = get_game_index()

    for game in games:
        print(f'{game["game_id"]} | {game["game"]} | {game["venue"]}')