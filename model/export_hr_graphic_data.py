from pathlib import Path
from utils.json_utils import load_json, save_json

ALL_GAMES_FILE = Path("data/processed/all_games.json")
OUTPUT_FILE = Path("data/processed/hr_targets.json")


def top_two(hitters):
    return sorted(
        hitters,
        key=lambda h: float(h.get("Likely") or 0),
        reverse=True,
    )[:2]


def clean_player(hitter):
    return {
        "player": hitter.get("Player", ""),
        "team": hitter.get("Team", ""),
        "bats": hitter.get("Bats", ""),
        "likely": hitter.get("Likely", ""),
        "alpha_score": hitter.get("Test Score", ""),
        "ceiling": hitter.get("Ceiling", ""),
        "hr_form": hitter.get("HR Form", ""),
        "khr": hitter.get("kHR", ""),
        "iso": hitter.get("ISO", ""),
        "xwoba": hitter.get("xwOBA", ""),
        "brl_bip": hitter.get("Brl/BIP%", ""),
        "hh": hitter.get("HH%", ""),
        "la": hitter.get("LA", ""),
    }


def export_hr_graphic_data():
    games = load_json(ALL_GAMES_FILE, default=[])
    output = []

    for game in games:
        away_hitters = game.get("hitters", {}).get("away", [])
        home_hitters = game.get("hitters", {}).get("home", [])

        away_targets = [clean_player(h) for h in top_two(away_hitters)]
        home_targets = [clean_player(h) for h in top_two(home_hitters)]

        output.append({
            "game_id": game.get("game_id", ""),
            "game": game.get("game", ""),
            "game_time": game.get("game_time", ""),
            "venue": game.get("venue", ""),
            "away_team": game.get("away_team", ""),
            "home_team": game.get("home_team", ""),
            "away_targets": away_targets,
            "home_targets": home_targets,
            "weather": game.get("weather", {}),
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, OUTPUT_FILE)

    print(f"✅ Exported HR graphic data for {len(output)} games")
    print(f"📁 {OUTPUT_FILE}")


if __name__ == "__main__":
    export_hr_graphic_data()