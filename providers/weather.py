import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from model.game_selector import get_game_index
from utils.json_utils import save_json

load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

STADIUM_FILE = Path("data/reference/stadium_weather.csv")
OUTPUT_FILE = Path("data/processed/weather.json")


def normalize(value):
    return str(value or "").strip().lower()


def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def wind_to_baseball_terms(wind_deg, center_field_deg):
    """
    OpenWeather wind deg = direction wind comes FROM.
    Convert to direction wind is blowing TO.
    """
    if wind_deg is None:
        return "NEUTRAL"

    wind_to = (float(wind_deg) + 180) % 360
    cf = float(center_field_deg)

    diff_cf = angle_diff(wind_to, cf)
    diff_in = angle_diff(wind_to, (cf + 180) % 360)

    rf = (cf + 35) % 360
    lf = (cf - 35) % 360

    diff_rf = angle_diff(wind_to, rf)
    diff_lf = angle_diff(wind_to, lf)

    if diff_cf <= 35:
        return "OUT"
    if diff_rf <= 30:
        return "OUT TOWARDS RF"
    if diff_lf <= 30:
        return "OUT TOWARDS LF"
    if diff_in <= 35:
        return "IN"

    return "NEUTRAL"


def load_stadium_lookup():
    df = pd.read_csv(STADIUM_FILE)

    return {
        normalize(row["venue"]): row.to_dict()
        for _, row in df.iterrows()
    }


def fetch_weather(lat, lon):
    if not OPENWEATHER_API_KEY:
        raise ValueError("OPENWEATHER_API_KEY missing from .env")

    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?lat={lat}&lon={lon}"
        f"&appid={OPENWEATHER_API_KEY}"
        "&units=imperial"
    )

    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def build_weather_file():
    games = get_game_index()
    stadiums = load_stadium_lookup()

    weather_rows = []

    for game in games:
        venue = game.get("venue", "")
        stadium = stadiums.get(normalize(venue))

        if not stadium:
            print(f"⚠️ Missing stadium weather reference for {venue}")
            continue

        try:
            data = fetch_weather(stadium["lat"], stadium["lon"])

            temp = data.get("main", {}).get("temp")
            humidity = data.get("main", {}).get("humidity")
            conditions = data.get("weather", [{}])[0].get("description", "")
            wind_speed = data.get("wind", {}).get("speed", 0)
            wind_deg = data.get("wind", {}).get("deg")

            wind_direction = wind_to_baseball_terms(
                wind_deg,
                stadium.get("center_field_deg", 0),
            )

            weather_rows.append({
                "game_id": game.get("game_id"),
                "game": game.get("game"),
                "venue": venue,
                "temperature": round(float(temp), 1) if temp is not None else "",
                "humidity": humidity,
                "conditions": conditions.title(),
                "wind_direction": wind_direction,
                "wind_speed": round(float(wind_speed), 1),
                "wind_degrees": wind_deg,
                "roof": stadium.get("roof", "open"),
            })

            print(f"✅ Weather: {game.get('game')} — {venue}")

        except Exception as e:
            print(f"⚠️ Weather failed for {venue}: {e}")

    save_json(weather_rows, OUTPUT_FILE)

    print(f"✅ Saved weather for {len(weather_rows)} parks")
    print(f"📁 {OUTPUT_FILE}")

    return weather_rows


if __name__ == "__main__":
    build_weather_file()