import json
from pathlib import Path


GAMES_DIR = Path("data/processed/games")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    games = []

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)
        games.append({
            "game_id": game["game_id"],
            "game": game["game"],
            "status": game.get("lineup_status", "missing"),
            "away_hitters": len(game.get("away_hitters", [])),
            "home_hitters": len(game.get("home_hitters", [])),
        })

    games.sort(key=lambda x: x["game"])

    print("\nLineup Status")
    print("=" * 70)

    for game in games:
        print(
            f'{game["game_id"]} | {game["game"]} | '
            f'{game["status"]} | '
            f'Away hitters: {game["away_hitters"]} | '
            f'Home hitters: {game["home_hitters"]}'
        )


if __name__ == "__main__":
    main()