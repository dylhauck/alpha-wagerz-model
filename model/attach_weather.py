from pathlib import Path

from utils.json_utils import load_json, save_json

GAMES_DIR = Path("data/processed/games")
WEATHER_FILE = Path("data/processed/weather.json")


VENUE_ALIASES = {
    "Rate Field": "Guaranteed Rate Field",
    "Guaranteed Rate Field": "Rate Field",
}


def normalize(value):
    return (
        str(value or "")
        .strip()
        .lower()
        .replace(".", "")
        .replace("&", "and")
    )


def venue_keys(value):
    raw = str(value or "").strip()
    alias = VENUE_ALIASES.get(raw)

    keys = {normalize(raw)}

    if alias:
        keys.add(normalize(alias))

    return keys


def build_weather_lookup():
    weather_data = load_json(WEATHER_FILE, default=[])

    lookup = {}

    for item in weather_data:
        venue = item.get("venue") or item.get("stadium")
        for key in venue_keys(venue):
            if key:
                lookup[key] = item

    return lookup


def attach_weather_to_games():
    weather_lookup = build_weather_lookup()

    if not weather_lookup:
        print("⚠️ No weather data found to attach.")
        return

    updated = 0
    missing = []

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})

        if not game:
            continue

        game_venue = game.get("venue", "")
        weather = None

        for key in venue_keys(game_venue):
            if key in weather_lookup:
                weather = weather_lookup[key]
                break

        if not weather:
            missing.append(game_venue)
            continue

        weather_payload = {
            "temperature": weather.get("temperature"),
            "humidity": weather.get("humidity"),
            "conditions": weather.get("conditions"),
            "wind_direction": weather.get("wind_direction"),
            "wind_speed": weather.get("wind_speed"),
            "wind_degrees": weather.get("wind_degrees"),
        }

        game["weather"] = weather_payload
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