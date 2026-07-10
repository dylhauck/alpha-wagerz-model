import json
from pathlib import Path

GAMES_DIR = Path("data/processed/games")
OUTPUT_FILE = Path("data/processed/rankings.json")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_game_hitters(game, side):
    hitters = game.get("hitters", {})

    if isinstance(hitters, dict):
        return hitters.get(side, [])

    if side == "away":
        return game.get("away_hitters", [])

    if side == "home":
        return game.get("home_hitters", [])

    return []

def build_rankings():
    hr_targets = []
    pitchers = []

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)

        for side in ["away", "home"]:
            for hitter in get_game_hitters(game, side):
                likely = hitter.get("Likely", "")
                if likely != "":
                    hr_targets.append({
                        "Category": "HR Target",
                        "Player/Team": hitter.get("Player", ""),
                        "Game": game.get("game", ""),
                        "Score": likely,
                        "Notes": "",
                    })

        for pitcher in game.get("pitchers", []):
            score = pitcher.get("Strikeout Score", "")
            if score != "":
                pitchers.append({
                    "Category": "Pitcher K Target",
                    "Player/Team": pitcher.get("Pitcher", ""),
                    "Game": game.get("game", ""),
                    "Score": score,
                    "Notes": "",
                })

    hr_targets.sort(key=lambda x: float(x["Score"]), reverse=True)
    pitchers.sort(key=lambda x: float(x["Score"]), reverse=True)

    rankings = {
        "hr_targets": hr_targets[:20],
        "pitchers": pitchers[:20],
    }

    save_json(rankings, OUTPUT_FILE)

    print("✅ Built rankings")
    print(f"📁 {OUTPUT_FILE}")


if __name__ == "__main__":
    build_rankings()