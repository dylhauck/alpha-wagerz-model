import json
from pathlib import Path

GAMES_DIR = Path("data/processed/games")
ALL_GAMES_FILE = Path("data/processed/all_games.json")
WEATHER_FILE = Path("data/processed/weather.json")
RANKINGS_FILE = Path("data/processed/rankings.json")


def load_json(filepath):
    if not filepath.exists():
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_game_hitters(game, side):
    hitters = game.get("hitters", {})

    if isinstance(hitters, dict):
        return hitters.get(side, [])

    if side == "away":
        return game.get("away_hitters", [])

    if side == "home":
        return game.get("home_hitters", [])

    return []

def validate_pipeline():
    errors = []
    warnings = []

    if not GAMES_DIR.exists():
        errors.append("Missing data/processed/games folder")

    game_files = list(GAMES_DIR.glob("*.json")) if GAMES_DIR.exists() else []

    if not game_files:
        errors.append("No processed game files found")

    if not ALL_GAMES_FILE.exists():
        errors.append("Missing data/processed/all_games.json")

    if not WEATHER_FILE.exists():
        warnings.append("Missing data/processed/weather.json")

    if not RANKINGS_FILE.exists():
        warnings.append("Missing data/processed/rankings.json")

    for file in game_files:
        game = load_json(file)

        if not game:
            errors.append(f"{file.name} is empty or invalid")
            continue

        game_name = game.get("game", file.name)

        if not game.get("game_id"):
            errors.append(f"{game_name}: missing game_id")

        if not game.get("away_team") or not game.get("home_team"):
            errors.append(f"{game_name}: missing team names")

        if not game.get("venue"):
            warnings.append(f"{game_name}: missing venue")

        if not game.get("away_sp") or not game.get("home_sp"):
            warnings.append(f"{game_name}: missing probable pitcher")

        away_hitters = get_game_hitters(game, "away")
        home_hitters = get_game_hitters(game, "home")

        if not away_hitters:
            warnings.append(f"{game_name}: missing away hitters")

        if not home_hitters:
            warnings.append(f"{game_name}: missing home hitters")

        weather = game.get("weather", {})

        if not weather:
            warnings.append(f"{game_name}: missing weather object")

        for side_name, hitters in [("away", away_hitters), ("home", home_hitters)]:
            for hitter in hitters:
                if hitter.get("Likely", "") == "":
                    warnings.append(
                        f"{game_name}: {side_name} hitter {hitter.get('Player', '')} missing Likely"
                    )

    print("\n🔎 Alpha Wagerz Pipeline Validation")
    print("=" * 45)

    if errors:
        print("\n❌ Errors:")
        for error in errors:
            print(f" - {error}")
    else:
        print("\n✅ No critical errors")

    if warnings:
        print("\n⚠️ Warnings:")
        for warning in warnings[:50]:
            print(f" - {warning}")

        if len(warnings) > 50:
            print(f" ... and {len(warnings) - 50} more warnings")
    else:
        print("\n✅ No warnings")

    print("\nValidation complete.")

    return {
        "errors": errors,
        "warnings": warnings,
    }


if __name__ == "__main__":
    validate_pipeline()