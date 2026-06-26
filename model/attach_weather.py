import json
from pathlib import Path

GAMES_DIR = Path("data/processed/games")
WEATHER_FILE = Path("data/processed/weather.json")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def normalize(value):
    return str(value or "").strip().lower()


def build_weather_lookup():
    if not WEATHER_FILE.exists():
        print(f"⚠️ Missing weather file: {WEATHER_FILE}")
        return {}

    weather_data = load_json(WEATHER_FILE)
    lookup = {}

    for item in weather_data:
        venue = normalize(item.get("venue") or item.get("stadium"))
        if venue:
            lookup[venue] = item

    return lookup


def attach_weather_to_games():
    weather_lookup = build_weather_lookup()

    if not weather_lookup:
        print("⚠️ No weather data found to attach.")
        return

    updated = 0
    missing = []

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)

        venue = normalize(game.get("venue"))
        weather = weather_lookup.get(venue)

        if not weather:
            missing.append(game.get("venue", "Unknown venue"))
            continue

        weather_payload = {
            "temperature": weather.get("temperature"),
            "humidity": weather.get("humidity"),
            "conditions": weather.get("conditions"),
            "wind_direction": weather.get("wind_direction"),
            "wind_speed": weather.get("wind_speed"),
        }

        # Store weather as a nested object
        game["weather"] = weather_payload

        # Also store top-level fields for scoring convenience
        game["temperature"] = weather_payload["temperature"]
        game["humidity"] = weather_payload["humidity"]
        game["conditions"] = weather_payload["conditions"]
        game["wind_direction"] = weather_payload["wind_direction"]
        game["wind_speed"] = weather_payload["wind_speed"]

        save_json(game, file)
        updated += 1

    print(f"✅ Attached weather to {updated} game files")

    if missing:
        print("⚠️ Missing weather for these venues:")
        for venue in sorted(set(missing)):
            print(f" - {venue}")


if __name__ == "__main__":
    attach_weather_to_games()