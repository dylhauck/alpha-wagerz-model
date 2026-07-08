import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

from model.game_selector import get_game_index
from utils.json_utils import save_json

load_dotenv(dotenv_path=Path.cwd() / ".env")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

STADIUM_FILE = Path("data/reference/stadium_weather.csv")
VENUE_ALIASES = {
    "uniqlo field at dodger stadium": "dodger stadium",
}
OUTPUT_FILE = Path("data/processed/weather.json")


def normalize(value):
    return str(value or "").strip().lower()


def angle_diff(a, b):
    return abs((a - b + 180) % 360 - 180)


def wind_to_baseball_terms(wind_deg, center_field_deg):
    if wind_deg is None:
        return "NEUTRAL"

    wind_to = (float(wind_deg) + 180) % 360
    cf = float(center_field_deg)

    diff_cf = angle_diff(wind_to, cf)
    diff_in = angle_diff(wind_to, (cf + 180) % 360)

    rf = (cf + 35) % 360
    lf = (cf - 35) % 360

    if diff_cf <= 35:
        return "OUT"
    if angle_diff(wind_to, rf) <= 30:
        return "OUT TOWARDS RF"
    if angle_diff(wind_to, lf) <= 30:
        return "OUT TOWARDS LF"
    if diff_in <= 35:
        return "IN"

    return "NEUTRAL"


def load_stadium_lookup():
    df = pd.read_csv(STADIUM_FILE)
    return {normalize(row["venue"]): row.to_dict() for _, row in df.iterrows()}


def fetch_forecast(lat, lon):
    if not OPENWEATHER_API_KEY:
        raise ValueError("OPENWEATHER_API_KEY missing from .env")

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={lat}&lon={lon}"
        f"&appid={OPENWEATHER_API_KEY}"
        "&units=imperial"
    )

    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def parse_game_datetime(game):
    for key in ["game_datetime_utc", "commence_time", "game_date_utc", "game_time_utc"]:
        value = game.get(key)
        if value:
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except Exception:
                pass

    value = game.get("game_datetime")
    if value:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass

    return None


def closest_forecast(forecast_data, target_dt):
    forecasts = forecast_data.get("list", [])

    if not forecasts:
        return None

    if not target_dt:
        return forecasts[0]

    if target_dt.tzinfo is None:
        target_dt = target_dt.replace(tzinfo=timezone.utc)

    def diff_seconds(item):
        item_dt = datetime.fromtimestamp(item.get("dt", 0), tz=timezone.utc)
        return abs((item_dt - target_dt).total_seconds())

    return min(forecasts, key=diff_seconds)


def build_weather_file():
    games = get_game_index()
    stadiums = load_stadium_lookup()

    weather_rows = []

    for game in games:
        venue = game.get("venue", "")
        venue_key = VENUE_ALIASES.get(normalize(venue), normalize(venue))
        stadium = stadiums.get(venue_key)

        if not stadium:
            print(f"⚠️ Missing stadium weather reference for {venue}")
            continue

        try:
            forecast_data = fetch_forecast(stadium["lat"], stadium["lon"])
            game_dt = parse_game_datetime(game)
            data = closest_forecast(forecast_data, game_dt)

            if not data:
                print(f"⚠️ No forecast data for {game.get('game')} — {venue}")
                continue

            temp = data.get("main", {}).get("temp")
            humidity = data.get("main", {}).get("humidity")
            conditions = data.get("weather", [{}])[0].get("description", "")
            wind_speed = data.get("wind", {}).get("speed", 0)
            wind_deg = data.get("wind", {}).get("deg")

            wind_direction = wind_to_baseball_terms(
                wind_deg,
                stadium.get("center_field_deg", 0),
            )

            forecast_time_utc = datetime.fromtimestamp(
                data.get("dt", 0),
                tz=timezone.utc,
            ).isoformat()

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
                "forecast_time_utc": forecast_time_utc,
            })

            print(f"✅ Forecast weather: {game.get('game')} — {venue}")

        except Exception as e:
            print(f"⚠️ Weather failed for {venue}: {e}")

    save_json(weather_rows, OUTPUT_FILE)

    print(f"✅ Saved weather for {len(weather_rows)} parks")
    print(f"📁 {OUTPUT_FILE}")

    return weather_rows


if __name__ == "__main__":
    build_weather_file()