import json
from pathlib import Path

from utils.file_utils import save_json

RAW_WEATHER_FILE = Path("data/manual/weather_today.json")
OUTPUT_FILE = Path("data/processed/weather.json")


def load_json(filepath):
    if not filepath.exists():
        return []

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def build_weather_file():
    weather = load_json(RAW_WEATHER_FILE)

    if not weather:
        print(f"⚠️ No manual weather found at {RAW_WEATHER_FILE}")
        print("Create this file first or paste today's weather into it.")
        return []

    save_json(weather, OUTPUT_FILE)

    print(f"✅ Saved weather file with {len(weather)} parks")
    print(f"📁 {OUTPUT_FILE}")

    return weather


if __name__ == "__main__":
    build_weather_file()