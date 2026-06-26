import json
from pathlib import Path

LINEUPS_FILE = Path("data/processed/lineups.json")
GAMES_DIR = Path("data/processed/games")


def load_json(filepath):
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def attach_lineups_to_games():
    lineups = load_json(LINEUPS_FILE)
    attached_count = 0

    for lineup in lineups:
        game_id = str(lineup["game_id"])
        game_file = GAMES_DIR / f"{game_id}.json"

        if not game_file.exists():
            print(f"⚠️ Missing game file for {game_id}")
            continue

        game = load_json(game_file)

        game["lineup_status"] = lineup.get("lineup_status", "")
        game["away_team_id"] = lineup.get("away_team_id")
        game["home_team_id"] = lineup.get("home_team_id")
        game["away_hitters"] = lineup.get("away_hitters", [])
        game["home_hitters"] = lineup.get("home_hitters", [])

        save_json(game, game_file)
        attached_count += 1

    print(f"✅ Attached lineups to {attached_count} game files")


if __name__ == "__main__":
    attach_lineups_to_games()