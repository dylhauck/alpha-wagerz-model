from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from dotenv import load_dotenv

from utils.json_utils import load_json, save_json


load_dotenv(dotenv_path=Path.cwd() / ".env")

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

STADIUM_FILE = Path("data/reference/stadium_weather.csv")

TOMORROW_GAMES_FILE = Path(
    "data/tomorrow/all_games.json"
)

OUTPUT_FILE = Path(
    "data/tomorrow/weather.json"
)

VENUE_ALIASES = {
    "uniqlo field at dodger stadium": "dodger stadium",
}


def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def angle_diff(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def wind_to_baseball_terms(
    wind_deg: float | None,
    center_field_deg: float,
) -> str:
    if wind_deg is None:
        return "NEUTRAL"

    wind_to = (float(wind_deg) + 180) % 360
    center_field = float(center_field_deg)

    diff_center = angle_diff(
        wind_to,
        center_field,
    )

    diff_in = angle_diff(
        wind_to,
        (center_field + 180) % 360,
    )

    right_field = (center_field + 35) % 360
    left_field = (center_field - 35) % 360

    if diff_center <= 35:
        return "OUT"

    if angle_diff(wind_to, right_field) <= 30:
        return "OUT TOWARDS RF"

    if angle_diff(wind_to, left_field) <= 30:
        return "OUT TOWARDS LF"

    if diff_in <= 35:
        return "IN"

    return "NEUTRAL"


def load_stadium_lookup() -> dict[str, dict[str, Any]]:
    if not STADIUM_FILE.exists():
        raise FileNotFoundError(
            f"Stadium weather file was not found: "
            f"{STADIUM_FILE}"
        )

    dataframe = pd.read_csv(STADIUM_FILE)

    return {
        normalize(row["venue"]): row.to_dict()
        for _, row in dataframe.iterrows()
    }


def load_tomorrow_games() -> list[dict[str, Any]]:
    if not TOMORROW_GAMES_FILE.exists():
        raise FileNotFoundError(
            f"Tomorrow all-games file was not found: "
            f"{TOMORROW_GAMES_FILE}"
        )

    games = load_json(
        TOMORROW_GAMES_FILE,
        default=[],
    )

    if not isinstance(games, list):
        raise ValueError(
            f"Expected a list in {TOMORROW_GAMES_FILE}"
        )

    return games


def fetch_forecast(
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    if not OPENWEATHER_API_KEY:
        raise ValueError(
            "OPENWEATHER_API_KEY is missing from .env"
        )

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
    )

    response = requests.get(
        url,
        params={
            "lat": latitude,
            "lon": longitude,
            "appid": OPENWEATHER_API_KEY,
            "units": "imperial",
        },
        headers={
            "Accept": "application/json",
            "User-Agent": "Alpha-Wagerz/1.0",
        },
        timeout=20,
    )

    response.raise_for_status()

    return response.json()


def parse_game_datetime(
    game: dict[str, Any],
) -> datetime | None:
    possible_fields = [
        "game_datetime_utc",
        "commence_time",
        "game_date_utc",
        "game_time_utc",
        "game_datetime",
    ]

    for field in possible_fields:
        value = game.get(field)

        if not value:
            continue

        try:
            parsed = datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc,
                )

            return parsed
        except (TypeError, ValueError):
            continue

    return None


def closest_forecast(
    forecast_data: dict[str, Any],
    target_datetime: datetime | None,
) -> dict[str, Any] | None:
    forecasts = forecast_data.get("list", [])

    if not forecasts:
        return None

    if target_datetime is None:
        return forecasts[0]

    if target_datetime.tzinfo is None:
        target_datetime = target_datetime.replace(
            tzinfo=timezone.utc,
        )

    def difference_seconds(
        forecast: dict[str, Any],
    ) -> float:
        forecast_datetime = datetime.fromtimestamp(
            forecast.get("dt", 0),
            tz=timezone.utc,
        )

        return abs(
            (
                forecast_datetime
                - target_datetime
            ).total_seconds()
        )

    return min(
        forecasts,
        key=difference_seconds,
    )


def build_tomorrow_weather_file() -> list[dict[str, Any]]:
    games = load_tomorrow_games()
    stadiums = load_stadium_lookup()

    weather_rows: list[dict[str, Any]] = []

    for game in games:
        venue = str(
            game.get("venue") or ""
        ).strip()

        venue_key = VENUE_ALIASES.get(
            normalize(venue),
            normalize(venue),
        )

        stadium = stadiums.get(venue_key)

        if not stadium:
            print(
                "⚠️ Missing stadium weather reference "
                f"for {venue}"
            )
            continue

        try:
            forecast_data = fetch_forecast(
                float(stadium["lat"]),
                float(stadium["lon"]),
            )

            game_datetime = parse_game_datetime(game)

            forecast = closest_forecast(
                forecast_data,
                game_datetime,
            )

            if not forecast:
                print(
                    "⚠️ No tomorrow forecast data for "
                    f"{game.get('game')} — {venue}"
                )
                continue

            main_data = forecast.get("main", {})
            wind_data = forecast.get("wind", {})
            weather_data = (
                forecast.get("weather", [{}]) or [{}]
            )[0]

            temperature = main_data.get("temp")
            humidity = main_data.get("humidity")
            conditions = weather_data.get(
                "description",
                "",
            )

            wind_speed = wind_data.get("speed", 0)
            wind_degrees = wind_data.get("deg")

            wind_direction = wind_to_baseball_terms(
                wind_degrees,
                float(
                    stadium.get(
                        "center_field_deg",
                        0,
                    )
                ),
            )

            forecast_time_utc = datetime.fromtimestamp(
                forecast.get("dt", 0),
                tz=timezone.utc,
            ).isoformat()

            weather_rows.append(
                {
                    "game_id": str(
                        game.get("game_id") or ""
                    ),
                    "game": game.get("game", ""),
                    "venue": venue,
                    "temperature": (
                        round(float(temperature), 1)
                        if temperature is not None
                        else ""
                    ),
                    "humidity": humidity,
                    "conditions": str(
                        conditions
                    ).title(),
                    "wind_direction": wind_direction,
                    "wind_speed": round(
                        float(wind_speed or 0),
                        1,
                    ),
                    "wind_degrees": wind_degrees,
                    "roof": stadium.get(
                        "roof",
                        "open",
                    ),
                    "forecast_time_utc": (
                        forecast_time_utc
                    ),
                }
            )

            print(
                "✅ Tomorrow weather: "
                f"{game.get('game')} — {venue}"
            )

        except Exception as error:
            print(
                f"⚠️ Tomorrow weather failed "
                f"for {venue}: {error}"
            )

    save_json(
        weather_rows,
        OUTPUT_FILE,
    )

    print(
        f"✅ Saved tomorrow weather for "
        f"{len(weather_rows)} park"
        f"{'' if len(weather_rows) == 1 else 's'}"
    )
    print(f"📁 {OUTPUT_FILE}")

    return weather_rows


if __name__ == "__main__":
    build_tomorrow_weather_file()