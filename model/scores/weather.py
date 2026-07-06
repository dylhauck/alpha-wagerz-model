import json
from pathlib import Path

WEATHER_THRESHOLDS_FILE = Path("data/reference/weather_thresholds.json")

DOME_ROOFS = {"dome", "closed"}
RETRACTABLE_ROOFS = {"retractable"}


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def normalize(value):
    return str(value or "").strip().lower().replace(" ", "_")


def safe_float(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def score_weather(game=None):
    if not game:
        return 50

    weather = game.get("weather", {})
    roof = normalize(weather.get("roof") or game.get("roof"))

    if roof in DOME_ROOFS:
        return 50

    temp = safe_float(weather.get("temperature", game.get("temperature")))
    wind_direction = normalize(weather.get("wind_direction", game.get("wind_direction")))
    wind_speed = safe_float(weather.get("wind_speed", game.get("wind_speed")))
    conditions = normalize(weather.get("conditions", game.get("conditions")))

    score = 50

    # Temperature impact
    if temp >= 95:
        score += 16
    elif temp >= 88:
        score += 12
    elif temp >= 80:
        score += 8
    elif temp >= 72:
        score += 4
    elif temp < 60:
        score -= 8
    elif temp < 68:
        score -= 4

    # Wind direction impact
    if "out_towards" in wind_direction:
        score += 10
    elif wind_direction == "out":
        score += 7
    elif "in_towards" in wind_direction:
        score -= 10
    elif wind_direction == "in":
        score -= 12
    elif wind_direction == "neutral":
        score += 0

    # Wind speed impact
    if "out" in wind_direction:
        score += min(wind_speed * 1.6, 18)
    elif "in" in wind_direction:
        score -= min(wind_speed * 1.8, 20)
    else:
        score += min(wind_speed * 0.25, 3)

    # Conditions impact
    if "clear" in conditions:
        score += 3
    elif "few_clouds" in conditions:
        score += 2
    elif "scattered_clouds" in conditions:
        score += 1
    elif "overcast" in conditions:
        score -= 2
    elif "rain" in conditions:
        score -= 8

    # Retractable roof = reduce impact
    if roof in RETRACTABLE_ROOFS:
        score = 50 + ((score - 50) * 0.55)

    return round(clamp(score), 1)