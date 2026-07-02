from pathlib import Path
from utils.json_utils import load_json, save_json

RAW_SLATE_FILE = Path("data/raw/todays_slate.json")
GAMES_DIR = Path("data/processed/games")


def attach_game_times():
    slate = load_json(RAW_SLATE_FILE, default=[])

    time_lookup = {
        str(game.get("game_id")): {
            "game_time": game.get("game_time", ""),
            "game_time_sort": game.get("game_time_sort", ""),
            "game_date_utc": game.get("game_date_utc", ""),
        }
        for game in slate
    }

    updated = 0

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})
        if not game:
            continue

        game_id = str(game.get("game_id", ""))
        time_data = time_lookup.get(game_id, {})

        game["game_time"] = time_data.get("game_time", "")
        game["game_time_sort"] = time_data.get("game_time_sort", "")
        game["game_date_utc"] = time_data.get("game_date_utc", "")

        save_json(game, file)
        updated += 1

    print(f"✅ Attached game times to {updated} games")


if __name__ == "__main__":
    attach_game_times()