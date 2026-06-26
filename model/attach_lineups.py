import json
from pathlib import Path


LINEUPS_FILE = Path("data/processed/lineups.json")
PROJECTED_FILE = Path("data/manual/projected_lineups.json")
GAMES_DIR = Path("data/processed/games")


def load_json(filepath):
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def attach_lineups_to_games():
    official_lineups = load_json(LINEUPS_FILE)
    projected_lineups = load_json(PROJECTED_FILE)

    attached_count = 0

    for lineup in official_lineups:
        game_id = lineup["game_id"]
        game_file = GAMES_DIR / f"{game_id}.json"

        if not game_file.exists():
            print(f"⚠️ Missing game file for {game_id}")
            continue

        game = load_json(game_file)

        if lineup["lineup_status"] == "confirmed":
            game["lineup_status"] = "confirmed"
            game["away_hitters"] = lineup["away_hitters"]
            game["home_hitters"] = lineup["home_hitters"]
        elif game_id in projected_lineups:
            projected = projected_lineups[game_id]
            game["lineup_status"] = "projected"
            game["away_hitters"] = projected.get("away_hitters", [])
            game["home_hitters"] = projected.get("home_hitters", [])
        else:
            game["lineup_status"] = "unconfirmed"
            game["away_hitters"] = []
            game["home_hitters"] = []

        save_json(game, game_file)
        attached_count += 1

    print(f"✅ Attached lineups to {attached_count} game files")


if __name__ == "__main__":
    attach_lineups_to_games()