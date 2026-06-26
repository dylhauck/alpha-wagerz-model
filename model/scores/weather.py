import json
from pathlib import Path

WEATHER_THRESHOLDS_FILE = Path("data/reference/weather_thresholds.json")


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def load_weather_thresholds():
    with open(WEATHER_THRESHOLDS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


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

    rules = load_weather_thresholds()

    temp = safe_float(game.get("temperature"))
    wind_direction = normalize(game.get("wind_direction"))
    wind_speed = safe_float(game.get("wind_speed"))
    conditions = normalize(game.get("conditions"))

    score = rules["base"]

    if temp >= 85:
        score += rules["temperature"]["hot_85_plus"]
    elif temp >= 75:
        score += rules["temperature"]["warm_75_84"]
    elif temp >= 65:
        score += rules["temperature"]["mild_65_74"]
    else:
        score += rules["temperature"]["cool_under_65"]

    if "out_towards" in wind_direction:
        score += rules["wind"]["out_towards_rf_lf"]
    elif wind_direction == "out":
        score += rules["wind"]["out"]
    elif "in_towards" in wind_direction:
        score += rules["wind"]["in_towards_rf_lf"]
    elif wind_direction == "in":
        score += rules["wind"]["in"]
    elif wind_direction == "neutral":
        score += rules["wind"]["neutral"]

    score += wind_speed * rules["wind_speed_multiplier"]
    score += rules["conditions"].get(conditions, 0)

    return round(clamp(score), 1)