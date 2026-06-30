from pathlib import Path

from utils.json_utils import load_json

GAMES_DIR = Path("data/processed/games")

REQUIRED_HITTER_FIELDS = [
    "Player",
    "Player ID",
    "Matchup",
    "Test Score",
    "Ceiling",
    "Zone Fit",
    "HR Form",
    "kHR",
    "Likely",
    "Confidence",
]

REQUIRED_MODEL_FIELDS = [
    "Power",
    "Contact",
    "Pitcher",
    "Pitch Type",
    "Team",
    "Bullpen",
    "Weather",
    "Park",
    "Recent",
]

REQUIRED_PITCHER_FIELDS = [
    "Team",
    "Pitcher",
    "Opponent",
    "Pitch Score",
    "Strikeout Score",
    "HR Vulnerability",
    "Fly Ball Profile",
    "Barrel Profile",
    "xwOBA",
    "CSW%",
    "SwStr%",
    "Ball%",
    "Brl/BIP%",
    "FB%",
    "GB%",
    "HH%",
    "K%",
    "BB%",
    "HR/9",
]


def has_missing(value):
    return value == "" or value is None


def validate_model_features():
    missing_weather = []
    missing_hitter_fields = []
    missing_model_fields = []
    missing_pitcher_fields = []
    dome_games = []

    total_games = 0
    total_hitters = 0
    total_pitchers = 0

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})
        if not game:
            continue

        total_games += 1

        game_name = game.get("game", file.name)
        weather = game.get("weather", {})
        roof = str(weather.get("roof") or game.get("roof") or "").lower()

        if not weather:
            missing_weather.append(game_name)

        if roof in ["dome", "closed", "retractable"]:
            dome_games.append(f"{game_name} — {roof}")

        hitters = game.get("hitters", {})
        if isinstance(hitters, dict):
            for side in ["away", "home"]:
                for hitter in hitters.get(side, []):
                    total_hitters += 1
                    player = hitter.get("Player", "")

                    for field in REQUIRED_HITTER_FIELDS:
                        if has_missing(hitter.get(field, "")):
                            missing_hitter_fields.append(f"{game_name}: {player} missing {field}")

                    for field in REQUIRED_MODEL_FIELDS:
                        if has_missing(hitter.get(field, "")):
                            missing_model_fields.append(f"{game_name}: {player} missing {field}")

                for pitcher in game.get("pitchers", []):
                    pitcher_name = pitcher.get("Pitcher", "")

                    if not pitcher_name or str(pitcher_name).upper() in ["TBD", "TBA"]:
                        continue

                    total_pitchers += 1

                    for field in REQUIRED_PITCHER_FIELDS:
                        if has_missing(pitcher.get(field, "")):
                            missing_pitcher_fields.append(f"{game_name}: {pitcher_name} missing {field}")

    print("\n🧪 Alpha Model Feature Validation")
    print("=" * 50)
    print(f"Games checked: {total_games}")
    print(f"Hitters checked: {total_hitters}")
    print(f"Pitchers checked: {total_pitchers}")

    print(f"\nWeather missing games: {len(missing_weather)}")
    print(f"Hitter stat missing fields: {len(missing_hitter_fields)}")
    print(f"Hitter model missing fields: {len(missing_model_fields)}")
    print(f"Pitcher missing fields: {len(missing_pitcher_fields)}")

    if dome_games:
        print("\n🏟️ Roof-controlled games:")
        for item in dome_games[:20]:
            print(f" - {item}")

    if missing_weather:
        print("\n⚠️ Missing weather:")
        for item in missing_weather[:20]:
            print(f" - {item}")

    if missing_hitter_fields:
        print("\n⚠️ Missing hitter stat examples:")
        for item in missing_hitter_fields[:20]:
            print(f" - {item}")

    if missing_model_fields:
        print("\n⚠️ Missing hitter model examples:")
        for item in missing_model_fields[:20]:
            print(f" - {item}")

    if missing_pitcher_fields:
        print("\n⚠️ Missing pitcher examples:")
        for item in missing_pitcher_fields[:20]:
            print(f" - {item}")

    print("\n✅ Feature validation complete.")


if __name__ == "__main__":
    validate_model_features()