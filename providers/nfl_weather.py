from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# =========================================================
# PATHS
# =========================================================

MODEL_ROOT = Path(__file__).resolve().parents[1]

NFL_DIR = MODEL_ROOT / "data" / "processed" / "nfl"

WEB_NFL_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nfl"
)

SLATE_FILE = NFL_DIR / "slate.json"
NEXT_SLATE_FILE = NFL_DIR / "next" / "slate.json"

OUTPUT_FILE = NFL_DIR / "weather.json"
NEXT_OUTPUT_FILE = NFL_DIR / "next" / "weather.json"

WEB_OUTPUT_FILE = WEB_NFL_DIR / "weather.json"
NEXT_WEB_OUTPUT_FILE = WEB_NFL_DIR / "next" / "weather.json"


# =========================================================
# SETTINGS
# =========================================================

REQUEST_TIMEOUT = 20

OPEN_METEO_URL = (
    "https://api.open-meteo.com/v1/forecast"
)


# =========================================================
# TEAM NORMALIZATION
# =========================================================

TEAM_ALIASES = {
    "LA": "LAR",
    "JAC": "JAX",
    "WSH": "WAS",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}

def normalize_team(
    value: Any,
) -> str:
    if isinstance(value, dict):
        value = (
            value.get("abbreviation")
            or value.get("abbr")
            or value.get("team_abbr")
            or value.get("team")
            or value.get("name")
            or ""
        )

    team = str(
        value or ""
    ).strip().upper()

    return TEAM_ALIASES.get(
        team,
        team,
    )

def normalize_team(
    value: Any,
) -> str:
    if isinstance(value, dict):
        value = (
            value.get("abbreviation")
            or value.get("abbr")
            or value.get("team_abbr")
            or value.get("team")
            or value.get("name")
            or ""
        )

    team = str(
        value or ""
    ).strip().upper()

    return TEAM_ALIASES.get(
        team,
        team,
    )


def normalize_roof(
    value: Any,
) -> str:
    roof = str(
        value or ""
    ).strip().lower()

    if roof in {
        "outdoor",
        "outdoors",
        "open",
    }:
        return "outdoor"

    if roof in {
        "dome",
        "indoors",
        "indoor",
        "closed",
        "fixed",
    }:
        return "fixed"

    if roof in {
        "retractable",
        "retractable roof",
    }:
        return "retractable"

    return ""

# =========================================================
# STADIUM DATA
# =========================================================
#
# roof:
#
# outdoor
# fixed
# retractable
#
# Retractable stadiums still receive weather because
# roof decisions may not be known until close to kickoff.
# The model treats them less aggressively than true
# outdoor venues.
# =========================================================

STADIUMS = {
    "ARI": {
        "name": "State Farm Stadium",
        "latitude": 33.5276,
        "longitude": -112.2626,
        "roof": "retractable",
    },

    "ATL": {
        "name": "Mercedes-Benz Stadium",
        "latitude": 33.7554,
        "longitude": -84.4008,
        "roof": "retractable",
    },

    "BAL": {
        "name": "M&T Bank Stadium",
        "latitude": 39.2780,
        "longitude": -76.6227,
        "roof": "outdoor",
    },

    "BUF": {
        "name": "Highmark Stadium",
        "latitude": 42.7738,
        "longitude": -78.7868,
        "roof": "outdoor",
    },

    "CAR": {
        "name": "Bank of America Stadium",
        "latitude": 35.2258,
        "longitude": -80.8528,
        "roof": "outdoor",
    },

    "CHI": {
        "name": "Soldier Field",
        "latitude": 41.8623,
        "longitude": -87.6167,
        "roof": "outdoor",
    },

    "CIN": {
        "name": "Paycor Stadium",
        "latitude": 39.0954,
        "longitude": -84.5160,
        "roof": "outdoor",
    },

    "CLE": {
        "name": "Huntington Bank Field",
        "latitude": 41.5061,
        "longitude": -81.6995,
        "roof": "outdoor",
    },

    "DAL": {
        "name": "AT&T Stadium",
        "latitude": 32.7473,
        "longitude": -97.0945,
        "roof": "retractable",
    },

    "DEN": {
        "name": "Empower Field at Mile High",
        "latitude": 39.7439,
        "longitude": -105.0201,
        "roof": "outdoor",
    },

    "DET": {
        "name": "Ford Field",
        "latitude": 42.3400,
        "longitude": -83.0456,
        "roof": "fixed",
    },

    "GB": {
        "name": "Lambeau Field",
        "latitude": 44.5013,
        "longitude": -88.0622,
        "roof": "outdoor",
    },

    "HOU": {
        "name": "NRG Stadium",
        "latitude": 29.6847,
        "longitude": -95.4107,
        "roof": "retractable",
    },

    "IND": {
        "name": "Lucas Oil Stadium",
        "latitude": 39.7601,
        "longitude": -86.1639,
        "roof": "retractable",
    },

    "JAX": {
        "name": "EverBank Stadium",
        "latitude": 30.3239,
        "longitude": -81.6373,
        "roof": "outdoor",
    },

    "KC": {
        "name": "GEHA Field at Arrowhead Stadium",
        "latitude": 39.0489,
        "longitude": -94.4839,
        "roof": "outdoor",
    },

    "LV": {
        "name": "Allegiant Stadium",
        "latitude": 36.0908,
        "longitude": -115.1830,
        "roof": "fixed",
    },

    "LAC": {
        "name": "SoFi Stadium",
        "latitude": 33.9535,
        "longitude": -118.3392,
        "roof": "fixed",
    },

    "LAR": {
        "name": "SoFi Stadium",
        "latitude": 33.9535,
        "longitude": -118.3392,
        "roof": "fixed",
    },

    "MIA": {
        "name": "Hard Rock Stadium",
        "latitude": 25.9580,
        "longitude": -80.2389,
        "roof": "outdoor",
    },

    "MIN": {
        "name": "U.S. Bank Stadium",
        "latitude": 44.9736,
        "longitude": -93.2575,
        "roof": "fixed",
    },

    "NE": {
        "name": "Gillette Stadium",
        "latitude": 42.0909,
        "longitude": -71.2643,
        "roof": "outdoor",
    },

    "NO": {
        "name": "Caesars Superdome",
        "latitude": 29.9511,
        "longitude": -90.0812,
        "roof": "fixed",
    },

    "NYG": {
        "name": "MetLife Stadium",
        "latitude": 40.8135,
        "longitude": -74.0745,
        "roof": "outdoor",
    },

    "NYJ": {
        "name": "MetLife Stadium",
        "latitude": 40.8135,
        "longitude": -74.0745,
        "roof": "outdoor",
    },

    "PHI": {
        "name": "Lincoln Financial Field",
        "latitude": 39.9008,
        "longitude": -75.1675,
        "roof": "outdoor",
    },

    "PIT": {
        "name": "Acrisure Stadium",
        "latitude": 40.4468,
        "longitude": -80.0158,
        "roof": "outdoor",
    },

    "SEA": {
        "name": "Lumen Field",
        "latitude": 47.5952,
        "longitude": -122.3316,
        "roof": "outdoor",
    },

    "SF": {
        "name": "Levi's Stadium",
        "latitude": 37.4030,
        "longitude": -121.9700,
        "roof": "outdoor",
    },

    "TB": {
        "name": "Raymond James Stadium",
        "latitude": 27.9759,
        "longitude": -82.5033,
        "roof": "outdoor",
    },

    "TEN": {
        "name": "Nissan Stadium",
        "latitude": 36.1665,
        "longitude": -86.7713,
        "roof": "outdoor",
    },

    "WAS": {
        "name": "Northwest Stadium",
        "latitude": 38.9076,
        "longitude": -76.8645,
        "roof": "outdoor",
    },
}


# =========================================================
# BASIC HELPERS
# =========================================================

def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except Exception:
        return default


def save_json(
    payload: Any,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            ensure_ascii=False,
        )


def load_json(
    path: Path,
    default: Any = None,
) -> Any:
    if not path.exists():
        return default

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            return json.load(
                handle
            )

    except Exception:
        return default


def fetch_json(
    url: str,
) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Alpha-Wagerz/1.0",
        },
    )

    with urlopen(
        request,
        timeout=REQUEST_TIMEOUT,
    ) as response:
        return json.loads(
            response.read().decode(
                "utf-8"
            )
        )


# =========================================================
# GAME HELPERS
# =========================================================

def extract_team(
    game: dict[str, Any],
    side: str,
) -> str:
    direct = game.get(
        f"{side}_team"
    )

    if direct:
        return normalize_team(
            direct
        )

    value = game.get(
        side
    )

    return normalize_team(
        value
    )


def extract_game_id(
    game: dict[str, Any],
) -> str:
    return str(
        game.get("game_id")
        or game.get("id")
        or game.get("event_id")
        or ""
    )

def extract_kickoff(
    game: dict[str, Any],
) -> str:
    # First prefer a complete datetime if the
    # slate ever provides one in the future.
    candidates = [
        game.get("kickoff"),
        game.get("start_time"),
        game.get("datetime"),
    ]

    for value in candidates:
        if value:
            return str(value)

    # Current Alpha NFL slate stores these
    # separately:
    #
    # game_date: 2026-09-09
    # game_time: 20:20
    #
    # Keep this as stadium-local clock time.
    game_date = str(
        game.get("game_date")
        or ""
    ).strip()

    game_time = str(
        game.get("game_time")
        or ""
    ).strip()

    if game_date and game_time:
        return (
            f"{game_date}T{game_time}"
        )

    # Date-only fallback.
    if game_date:
        return game_date

    return ""

def parse_datetime(
    value: str,
) -> datetime | None:
    if not value:
        return None

    cleaned = value.replace(
        "Z",
        "+00:00",
    )

    try:
        return datetime.fromisoformat(
            cleaned
        )
    except Exception:
        return None


# =========================================================
# WEATHER CODE
# =========================================================

def weather_description(
    code: int,
) -> str:
    mapping = {
        0: "Clear",
        1: "Mainly Clear",
        2: "Partly Cloudy",
        3: "Overcast",

        45: "Fog",
        48: "Rime Fog",

        51: "Light Drizzle",
        53: "Drizzle",
        55: "Heavy Drizzle",

        56: "Freezing Drizzle",
        57: "Heavy Freezing Drizzle",

        61: "Light Rain",
        63: "Rain",
        65: "Heavy Rain",

        66: "Freezing Rain",
        67: "Heavy Freezing Rain",

        71: "Light Snow",
        73: "Snow",
        75: "Heavy Snow",

        77: "Snow Grains",

        80: "Rain Showers",
        81: "Rain Showers",
        82: "Heavy Rain Showers",

        85: "Snow Showers",
        86: "Heavy Snow Showers",

        95: "Thunderstorm",
        96: "Thunderstorm with Hail",
        99: "Severe Thunderstorm with Hail",
    }

    return mapping.get(
        int(code),
        "Unknown",
    )


# =========================================================
# FORECAST
# =========================================================

def fetch_forecast(
    latitude: float,
    longitude: float,
    kickoff: datetime,
) -> dict[str, Any]:
    date_string = kickoff.date().isoformat()

    params = {
        "latitude": latitude,
        "longitude": longitude,

        "hourly": (
            "temperature_2m,"
            "apparent_temperature,"
            "relative_humidity_2m,"
            "precipitation_probability,"
            "precipitation,"
            "weather_code,"
            "wind_speed_10m,"
            "wind_gusts_10m"
        ),

        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",

        "timezone": "auto",

        "start_date": date_string,
        "end_date": date_string,
    }

    url = (
        OPEN_METEO_URL
        + "?"
        + urlencode(params)
    )

    return fetch_json(
        url
    )


def nearest_weather_hour(
    forecast: dict[str, Any],
    kickoff: datetime,
) -> dict[str, Any]:
    hourly = forecast.get(
        "hourly",
        {}
    )

    times = hourly.get(
        "time",
        []
    )

    if not times:
        return {}

    best_index = None
    best_distance = None

    for index, raw_time in enumerate(
        times
    ):
        try:
            forecast_time = (
                datetime.fromisoformat(
                    raw_time
                )
            )

            candidate = kickoff

            if candidate.tzinfo:
                candidate = (
                    candidate.replace(
                        tzinfo=None
                    )
                )

            distance = abs(
                (
                    forecast_time
                    - candidate
                ).total_seconds()
            )

            if (
                best_distance is None
                or distance < best_distance
            ):
                best_distance = distance
                best_index = index

        except Exception:
            continue

    if best_index is None:
        return {}

    def value(
        key: str,
        default=None,
    ):
        values = hourly.get(
            key,
            []
        )

        if (
            best_index
            < len(values)
        ):
            return values[
                best_index
            ]

        return default

    weather_code = int(
        safe_float(
            value(
                "weather_code",
                0,
            )
        )
    )

    return {
        "forecast_time": value(
            "time"
        ),

        "temperature_f": safe_float(
            value(
                "temperature_2m"
            )
        ),

        "feels_like_f": safe_float(
            value(
                "apparent_temperature"
            )
        ),

        "humidity_pct": safe_float(
            value(
                "relative_humidity_2m"
            )
        ),

        "precip_probability_pct": safe_float(
            value(
                "precipitation_probability"
            )
        ),

        "precipitation_in": safe_float(
            value(
                "precipitation"
            )
        ),

        "wind_mph": safe_float(
            value(
                "wind_speed_10m"
            )
        ),

        "wind_gust_mph": safe_float(
            value(
                "wind_gusts_10m"
            )
        ),

        "weather_code": weather_code,

        "conditions": (
            weather_description(
                weather_code
            )
        ),
    }


# =========================================================
# WEATHER IMPACT
# =========================================================

def calculate_weather_context(
    weather: dict[str, Any],
    roof: str,
) -> dict[str, Any]:
    if roof == "fixed":
        return {
            "severity_score": 0.0,

            "passing_factor": 1.0,
            "rushing_factor": 1.0,
            "scoring_factor": 1.0,
            "kicking_factor": 1.0,

            "classification": "INDOOR",
        }

    wind = safe_float(
        weather.get(
            "wind_mph"
        )
    )

    gust = safe_float(
        weather.get(
            "wind_gust_mph"
        )
    )

    temperature = safe_float(
        weather.get(
            "temperature_f"
        ),
        70,
    )

    precip_probability = (
        safe_float(
            weather.get(
                "precip_probability_pct"
            )
        )
    )

    precip = safe_float(
        weather.get(
            "precipitation_in"
        )
    )

    severity = 0.0

    # Wind
    if wind >= 20:
        severity += 4.0
    elif wind >= 15:
        severity += 2.5
    elif wind >= 10:
        severity += 1.0

    if gust >= 30:
        severity += 2.0
    elif gust >= 25:
        severity += 1.0

    # Cold
    if temperature <= 20:
        severity += 2.0
    elif temperature <= 32:
        severity += 1.0

    # Rain / snow
    if precip >= 0.10:
        severity += 2.0
    elif precip > 0:
        severity += 1.0

    if precip_probability >= 70:
        severity += 1.0

    severity = min(
        severity,
        10.0,
    )

    # Retractable roofs receive smaller
    # pregame weather adjustments because
    # the roof may ultimately be closed.

    roof_multiplier = (
        0.45
        if roof == "retractable"
        else 1.0
    )

    effective = (
        severity
        * roof_multiplier
    )

    passing_factor = max(
        0.84,
        1.0
        - effective * 0.018,
    )

    scoring_factor = max(
        0.88,
        1.0
        - effective * 0.013,
    )

    kicking_factor = max(
        0.82,
        1.0
        - effective * 0.020,
    )

    rushing_factor = min(
        1.08,
        1.0
        + effective * 0.005,
    )

    if effective >= 6:
        classification = "SEVERE"

    elif effective >= 3.5:
        classification = "SIGNIFICANT"

    elif effective >= 1.5:
        classification = "MODERATE"

    elif effective > 0:
        classification = "MINOR"

    else:
        classification = "NEUTRAL"

    return {
        "severity_score": round(
            effective,
            2,
        ),

        "passing_factor": round(
            passing_factor,
            3,
        ),

        "rushing_factor": round(
            rushing_factor,
            3,
        ),

        "scoring_factor": round(
            scoring_factor,
            3,
        ),

        "kicking_factor": round(
            kicking_factor,
            3,
        ),

        "classification": (
            classification
        ),
    }


# =========================================================
# GAME WEATHER
# =========================================================

def build_game_weather(
    game: dict[str, Any],
) -> dict[str, Any]:
    away_team = extract_team(
        game,
        "away",
    )

    home_team = extract_team(
        game,
        "home",
    )

    game_id = extract_game_id(
        game
    )

    kickoff_raw = extract_kickoff(
        game
    )

    kickoff = parse_datetime(
        kickoff_raw
    )

    stadium = STADIUMS.get(
        home_team
    )

    if not stadium:
        return {
            "game_id": game_id,
            "away_team": away_team,
            "home_team": home_team,

            "available": False,

            "reason": (
                "stadium_not_found"
            ),
        }

    slate_roof = normalize_roof(
    game.get("roof")
    )

    roof = (
        slate_roof
        or stadium["roof"]
    )

    base = {
        "game_id": game_id,

        "away_team": away_team,
        "home_team": home_team,

        "stadium": stadium[
            "name"
        ],

        "latitude": stadium[
            "latitude"
        ],

        "longitude": stadium[
            "longitude"
        ],

        "roof": roof,

        "kickoff": kickoff_raw,
    }

    # Fixed roof = no outdoor weather impact.

    if roof == "fixed":
        context = (
            calculate_weather_context(
                {},
                roof,
            )
        )

        return {
            **base,

            "available": True,

            "weather": {
                "conditions": "Indoor",
            },

            "context": context,
        }

    if kickoff is None:
        return {
            **base,

            "available": False,

            "reason": (
                "kickoff_not_found"
            ),
        }

    try:
        forecast = fetch_forecast(
            stadium[
                "latitude"
            ],
            stadium[
                "longitude"
            ],
            kickoff,
        )

        weather = nearest_weather_hour(
            forecast,
            kickoff,
        )

    except Exception as exc:
        return {
            **base,

            "available": False,

            "reason": (
                f"forecast_error: {exc}"
            ),
        }

    if not weather:
        return {
            **base,

            "available": False,

            "reason": (
                "forecast_not_available"
            ),
        }

    context = (
        calculate_weather_context(
            weather,
            roof,
        )
    )

    return {
        **base,

        "available": True,

        "weather": weather,

        "context": context,
    }


# =========================================================
# BUILD SLATE
# =========================================================

def build_weather_file(
    slate_file: Path,
    output_file: Path,
    web_output_file: Path,
) -> dict[str, Any]:
    slate = load_json(
        slate_file,
        default={},
    )

    if isinstance(
        slate,
        list,
    ):
        games = slate

    elif isinstance(
        slate,
        dict,
    ):
        games = slate.get(
            "games",
            []
        )

    else:
        games = []

    weather_games = []

    for game in games:
        if not isinstance(
            game,
            dict,
        ):
            continue

        context = build_game_weather(
            game
        )

        weather_games.append(
            context
        )

        away = context.get(
            "away_team",
            "?",
        )

        home = context.get(
            "home_team",
            "?",
        )

        if context.get(
            "available"
        ):
            roof = context.get(
                "roof"
            )

            classification = (
                context.get(
                    "context",
                    {},
                ).get(
                    "classification",
                    "NEUTRAL",
                )
            )

            print(
                f"      {away} @ {home}: "
                f"{roof} / {classification}"
            )

        else:
            print(
                f"      {away} @ {home}: "
                f"⚠️ {context.get('reason')}"
            )

    payload = {
        "generated_at": (
            datetime.now(timezone.utc).isoformat()
        ),

        "source": "Open-Meteo",

        "games": weather_games,
    }

    save_json(
        payload,
        output_file,
    )

    save_json(
        payload,
        web_output_file,
    )

    print(
        f"\n   ✅ {len(weather_games)} "
        f"weather contexts"
    )

    print(
        f"      model: {output_file}"
    )

    print(
        f"      web:   {web_output_file}"
    )

    return payload


# =========================================================
# MAIN
# =========================================================

def build_nfl_weather():
    print(
        "\n🌦️ BUILDING NFL WEATHER "
        "CONTEXT\n"
    )

    if not SLATE_FILE.exists():
        raise RuntimeError(
            f"NFL slate not found: "
            f"{SLATE_FILE}"
        )

    print(
        "   Current slate"
    )

    current = build_weather_file(
        SLATE_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
    )

    next_payload = None

    if NEXT_SLATE_FILE.exists():
        print(
            "\n   Next slate"
        )

        next_payload = (
            build_weather_file(
                NEXT_SLATE_FILE,
                NEXT_OUTPUT_FILE,
                NEXT_WEB_OUTPUT_FILE,
            )
        )

    print(
        "\n✅ NFL WEATHER "
        "CONTEXT COMPLETE\n"
    )

    return {
        "current": current,
        "next": next_payload,
    }


if __name__ == "__main__":
    build_nfl_weather()