from pathlib import Path

from utils.json_utils import load_json, save_json

GAMES_DIR = Path("data/processed/games")
TEAM_CONTEXT_FILE = Path("data/processed/team_context.json")


def attach_team_standings():
    team_context = load_json(TEAM_CONTEXT_FILE, default={})
    updated = 0

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})
        if not game:
            continue

        away_team = game.get("away_team", "")
        home_team = game.get("home_team", "")

        game["away_team_context"] = team_context.get(away_team, {})
        game["home_team_context"] = team_context.get(home_team, {})

        save_json(game, file)
        updated += 1

    print(f"✅ Attached team standings/context to {updated} games")


if __name__ == "__main__":
    attach_team_standings()