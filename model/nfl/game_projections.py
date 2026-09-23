from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


MODEL_ROOT = Path(__file__).resolve().parents[2]

NFL_DIR = (
    MODEL_ROOT
    / "data"
    / "processed"
    / "nfl"
)

WEB_NFL_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nfl"
)

TEAM_METRICS_FILE = (
    NFL_DIR
    / "team_metrics.json"
)

MATCHUP_METRICS_FILE = (
    NFL_DIR
    / "matchup_metrics.json"
)

INJURY_CONTEXT_FILE = (
    NFL_DIR
    / "injury_context.json"
)

WEATHER_FILE = (
    NFL_DIR
    / "weather.json"
)

SLATE_FILE = (
    NFL_DIR
    / "slate.json"
)

OUTPUT_FILE = (
    NFL_DIR
    / "game_projections.json"
)

WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "game_projections.json"
)

NEXT_MATCHUP_METRICS_FILE = (
    NFL_DIR
    / "next"
    / "matchup_metrics.json"
)

NEXT_INJURY_CONTEXT_FILE = (
    NFL_DIR
    / "next"
    / "injury_context.json"
)

NEXT_WEATHER_FILE = (
    NFL_DIR
    / "next"
    / "weather.json"
)

NEXT_SLATE_FILE = (
    NFL_DIR
    / "next"
    / "slate.json"
)

NEXT_OUTPUT_FILE = (
    NFL_DIR
    / "next"
    / "game_projections.json"
)

NEXT_WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "next"
    / "game_projections.json"
)


# =========================================================
# MODEL SETTINGS
# =========================================================

LEAGUE_AVERAGE_POINTS = 22.5

HOME_FIELD_POINTS = 1.5

MIN_TEAM_POINTS = 10.0
MAX_TEAM_POINTS = 40.0

MIN_GAME_TOTAL = 28.0
MAX_GAME_TOTAL = 70.0


# =========================================================
# BASIC HELPERS
# =========================================================

def f(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value in (
            None,
            "",
        ):
            return default

        return float(value)

    except Exception:
        return default


def clean_text(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def normalize_team(
    value: Any,
) -> str:
    team = clean_text(
        value
    ).upper()

    aliases = {
        "LA": "LAR",
        "JAC": "JAX",
        "WSH": "WAS",
        "OAK": "LV",
        "SD": "LAC",
        "STL": "LAR",
    }

    return aliases.get(
        team,
        team,
    )


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def nested(
    payload: dict[str, Any],
    *keys: str,
    default=0.0,
):
    current: Any = payload

    for key in keys:
        if not isinstance(
            current,
            dict,
        ):
            return default

        current = current.get(
            key
        )

        if current is None:
            return default

    return current


def mean(
    values: list[float],
) -> float:
    values = [
        value
        for value in values
        if value is not None
    ]

    if not values:
        return 0.0

    return (
        sum(values)
        / len(values)
    )


# =========================================================
# TEAM LOOKUP
# =========================================================

def build_team_lookup(
    payload: Any,
):
    lookup: dict[
        str,
        dict[str, Any]
    ] = {}

    if isinstance(
        payload,
        dict,
    ):
        teams = payload.get(
            "teams",
            [],
        )

        if not teams:
            teams = []

            for key, value in (
                payload.items()
            ):
                if not isinstance(
                    value,
                    dict,
                ):
                    continue

                row = dict(
                    value
                )

                row.setdefault(
                    "team",
                    key,
                )

                teams.append(
                    row
                )

    elif isinstance(
        payload,
        list,
    ):
        teams = payload

    else:
        teams = []

    for row in teams:
        if not isinstance(
            row,
            dict,
        ):
            continue

        team = normalize_team(
            row.get(
                "team"
            )
        )

        if team:
            lookup[
                team
            ] = row

    return lookup


# =========================================================
# MATCHUP LOOKUP
# =========================================================

def build_matchup_lookup(
    payload: Any,
):
    lookup: dict[
        tuple[str, str],
        dict[str, Any]
    ] = {}

    games = (
        payload
        if isinstance(
            payload,
            list,
        )
        else payload.get(
            "games",
            [],
        )
        if isinstance(
            payload,
            dict,
        )
        else []
    )

    for game in games:
        if not isinstance(
            game,
            dict,
        ):
            continue

        away = normalize_team(
            game.get(
                "away_team"
            )
        )

        home = normalize_team(
            game.get(
                "home_team"
            )
        )

        if (
            away
            and home
        ):
            lookup[
                (
                    away,
                    home,
                )
            ] = game

    return lookup


# =========================================================
# INJURY CONTEXT LOOKUP
# =========================================================

def build_injury_lookup(
    payload: Any,
):
    lookup: dict[
        tuple[str, str],
        dict[str, Any]
    ] = {}

    games = (
        payload
        if isinstance(payload, list)
        else payload.get("games", [])
        if isinstance(payload, dict)
        else []
    )

    for game in games:
        if not isinstance(game, dict):
            continue

        away = normalize_team(
            game.get("away_team")
        )
        home = normalize_team(
            game.get("home_team")
        )

        if away and home:
            lookup[(away, home)] = game

    return lookup

def build_weather_lookup(
    payload: Any,
) -> dict[
    tuple[str, str],
    dict[str, Any]
]:
    lookup: dict[
        tuple[str, str],
        dict[str, Any]
    ] = {}

    if isinstance(
        payload,
        dict,
    ):
        games = payload.get(
            "games",
            [],
        )

    elif isinstance(
        payload,
        list,
    ):
        games = payload

    else:
        games = []

    for game in games:
        if not isinstance(
            game,
            dict,
        ):
            continue

        away_team = normalize_team(
            game.get(
                "away_team"
            )
        )

        home_team = normalize_team(
            game.get(
                "home_team"
            )
        )

        if (
            not away_team
            or not home_team
        ):
            continue

        lookup[
            (
                away_team,
                home_team,
            )
        ] = game

    return lookup

# =========================================================
# LEAGUE BASELINES
# =========================================================

def calculate_league_baselines(
    team_lookup: dict[
        str,
        dict[str, Any]
    ],
):
    offensive_points = []
    defensive_points = []

    offensive_epa = []
    defensive_epa = []

    offensive_success = []
    defensive_success = []

    offensive_ypp = []
    defensive_ypp = []

    offensive_explosive = []
    defensive_explosive = []

    offensive_third_down = []
    defensive_third_down = []

    offensive_red_zone = []
    defensive_red_zone = []

    offensive_turnovers = []
    defensive_takeaways = []

    for team in (
        team_lookup.values()
    ):
        offense = team.get(
            "offense",
            {},
        )

        defense = team.get(
            "defense",
            {},
        )

        points = f(
            offense.get(
                "points_per_game"
            )
        )

        if points:
            offensive_points.append(
                points
            )

        points_allowed = f(
            defense.get(
                "points_per_game"
            )
        )

        if points_allowed:
            defensive_points.append(
                points_allowed
            )

        offensive_epa.append(
            f(
                offense.get(
                    "epa_per_play"
                )
            )
        )

        defensive_epa.append(
            f(
                defense.get(
                    "epa_per_play"
                )
            )
        )

        offensive_success.append(
            f(
                offense.get(
                    "success_rate"
                )
            )
        )

        defensive_success.append(
            f(
                defense.get(
                    "success_rate"
                )
            )
        )

        offensive_ypp.append(
            f(
                offense.get(
                    "yards_per_play"
                )
            )
        )

        defensive_ypp.append(
            f(
                defense.get(
                    "yards_per_play"
                )
            )
        )

        offensive_explosive.append(
            f(
                offense.get(
                    "explosive_rate"
                )
            )
        )

        defensive_explosive.append(
            f(
                defense.get(
                    "explosive_rate"
                )
            )
        )

        offensive_third_down.append(
            f(
                offense.get(
                    "third_down_rate"
                )
            )
        )

        defensive_third_down.append(
            f(
                defense.get(
                    "third_down_rate"
                )
            )
        )

        offensive_red_zone.append(
            f(
                offense.get(
                    "red_zone_td_rate"
                )
            )
        )

        defensive_red_zone.append(
            f(
                defense.get(
                    "red_zone_td_rate"
                )
            )
        )

        offensive_turnovers.append(
            f(
                offense.get(
                    "turnovers_per_game"
                )
            )
        )

        defensive_takeaways.append(
            f(
                defense.get(
                    "turnovers_per_game"
                )
            )
        )

    league_points = mean(
        offensive_points
    )

    if not league_points:
        league_points = (
            LEAGUE_AVERAGE_POINTS
        )

    league_points_allowed = mean(
        defensive_points
    )

    if not league_points_allowed:
        league_points_allowed = (
            league_points
        )

    return {
        "points_per_game": (
            league_points
        ),

        "points_allowed_per_game": (
            league_points_allowed
        ),

        "offensive_epa": mean(
            offensive_epa
        ),

        "defensive_epa": mean(
            defensive_epa
        ),

        "offensive_success": mean(
            offensive_success
        ),

        "defensive_success": mean(
            defensive_success
        ),

        "offensive_ypp": mean(
            offensive_ypp
        ),

        "defensive_ypp": mean(
            defensive_ypp
        ),

        "offensive_explosive": mean(
            offensive_explosive
        ),

        "defensive_explosive": mean(
            defensive_explosive
        ),

        "offensive_third_down": mean(
            offensive_third_down
        ),

        "defensive_third_down": mean(
            defensive_third_down
        ),

        "offensive_red_zone": mean(
            offensive_red_zone
        ),

        "defensive_red_zone": mean(
            defensive_red_zone
        ),

        "offensive_turnovers": mean(
            offensive_turnovers
        ),

        "defensive_takeaways": mean(
            defensive_takeaways
        ),
    }


# =========================================================
# BASE TEAM SCORING
# =========================================================

def base_scoring_projection(
    offense: dict[str, Any],
    defense: dict[str, Any],
    league: dict[str, float],
):
    league_points = f(
        league.get(
            "points_per_game"
        ),
        LEAGUE_AVERAGE_POINTS,
    )

    if not league_points:
        league_points = (
            LEAGUE_AVERAGE_POINTS
        )

    offense_ppg = f(
        offense.get(
            "points_per_game"
        ),
        league_points,
    )

    defense_ppg = f(
        defense.get(
            "points_per_game"
        ),
        league_points,
    )

    if not offense_ppg:
        offense_ppg = (
            league_points
        )

    if not defense_ppg:
        defense_ppg = (
            league_points
        )

    # Blend the offense's scoring history
    # with the opponent's scoring allowed.
    #
    # Offense receives slightly more weight
    # because offensive identity is more
    # stable than raw opponent points allowed.

    projection = (
        offense_ppg * 0.56
        + defense_ppg * 0.44
    )

    return projection


# =========================================================
# EFFICIENCY ADJUSTMENT
# =========================================================

def efficiency_adjustment(
    offense: dict[str, Any],
    defense: dict[str, Any],
    league: dict[str, float],
):
    adjustments = []

    # EPA / play
    offense_epa_delta = (
        f(
            offense.get(
                "epa_per_play"
            )
        )
        - league[
            "offensive_epa"
        ]
    )

    defense_epa_delta = (
        f(
            defense.get(
                "epa_per_play"
            )
        )
        - league[
            "defensive_epa"
        ]
    )

    epa_adjustment = (
        (
            offense_epa_delta
            + defense_epa_delta
        )
        * 8.0
    )

    adjustments.append(
        (
            epa_adjustment,
            0.30,
        )
    )

    # Yards per play
    offense_ypp_delta = (
        f(
            offense.get(
                "yards_per_play"
            )
        )
        - league[
            "offensive_ypp"
        ]
    )

    defense_ypp_delta = (
        f(
            defense.get(
                "yards_per_play"
            )
        )
        - league[
            "defensive_ypp"
        ]
    )

    ypp_adjustment = (
        (
            offense_ypp_delta
            + defense_ypp_delta
        )
        * 1.8
    )

    adjustments.append(
        (
            ypp_adjustment,
            0.20,
        )
    )

    # Success rate
    offense_success_delta = (
        f(
            offense.get(
                "success_rate"
            )
        )
        - league[
            "offensive_success"
        ]
    )

    defense_success_delta = (
        f(
            defense.get(
                "success_rate"
            )
        )
        - league[
            "defensive_success"
        ]
    )

    success_adjustment = (
        (
            offense_success_delta
            + defense_success_delta
        )
        * 0.08
    )

    adjustments.append(
        (
            success_adjustment,
            0.18,
        )
    )

    # Explosive plays
    offense_explosive_delta = (
        f(
            offense.get(
                "explosive_rate"
            )
        )
        - league[
            "offensive_explosive"
        ]
    )

    defense_explosive_delta = (
        f(
            defense.get(
                "explosive_rate"
            )
        )
        - league[
            "defensive_explosive"
        ]
    )

    explosive_adjustment = (
        (
            offense_explosive_delta
            + defense_explosive_delta
        )
        * 0.10
    )

    adjustments.append(
        (
            explosive_adjustment,
            0.12,
        )
    )

    # Third down
    third_down_delta = (
        (
            f(
                offense.get(
                    "third_down_rate"
                )
            )
            - league[
                "offensive_third_down"
            ]
        )
        +
        (
            f(
                defense.get(
                    "third_down_rate"
                )
            )
            - league[
                "defensive_third_down"
            ]
        )
    )

    third_down_adjustment = (
        third_down_delta
        * 0.05
    )

    adjustments.append(
        (
            third_down_adjustment,
            0.08,
        )
    )

    # Red zone
    red_zone_delta = (
        (
            f(
                offense.get(
                    "red_zone_td_rate"
                )
            )
            - league[
                "offensive_red_zone"
            ]
        )
        +
        (
            f(
                defense.get(
                    "red_zone_td_rate"
                )
            )
            - league[
                "defensive_red_zone"
            ]
        )
    )

    red_zone_adjustment = (
        red_zone_delta
        * 0.05
    )

    adjustments.append(
        (
            red_zone_adjustment,
            0.08,
        )
    )

    # Turnovers
    offense_turnover_delta = (
        league[
            "offensive_turnovers"
        ]
        - f(
            offense.get(
                "turnovers_per_game"
            )
        )
    )

    defense_takeaway_delta = (
        f(
            defense.get(
                "turnovers_per_game"
            )
        )
        - league[
            "defensive_takeaways"
        ]
    )

    turnover_adjustment = (
        (
            offense_turnover_delta
            + defense_takeaway_delta
        )
        * 1.2
    )

    adjustments.append(
        (
            turnover_adjustment,
            0.04,
        )
    )

    return sum(
        value * weight
        for value, weight
        in adjustments
    )


# =========================================================
# MATCHUP ADJUSTMENT
# =========================================================

def matchup_adjustment(
    matchup: dict[str, Any],
):
    rating = f(
        matchup.get(
            "rating"
        )
    )

    passing_rating = f(
        nested(
            matchup,
            "passing",
            "rating",
        )
    )

    rushing_rating = f(
        nested(
            matchup,
            "rushing",
            "rating",
        )
    )

    overall_adjustment = (
        rating * 0.045
    )

    passing_adjustment = (
        passing_rating * 0.020
    )

    rushing_adjustment = (
        rushing_rating * 0.012
    )

    adjustment = (
        overall_adjustment
        + passing_adjustment
        + rushing_adjustment
    )

    return clamp(
        adjustment,
        -5.0,
        5.0,
    )


# =========================================================
# TEAM PROJECTION
# =========================================================

def project_team_points(
    offense_team: str,
    defense_team: str,
    team_lookup: dict[
        str,
        dict[str, Any]
    ],
    matchup: dict[str, Any],
    league: dict[str, float],
    home: bool,
    injury_context: dict[str, Any] | None = None,
    weather_context: dict[str, Any] | None = None,
):
    offense_team_row = (
        team_lookup.get(
            offense_team,
            {}
        )
    )

    defense_team_row = (
        team_lookup.get(
            defense_team,
            {}
        )
    )

    offense = (
        offense_team_row.get(
            "offense",
            {},
        )
    )

    defense = (
        defense_team_row.get(
            "defense",
            {},
        )
    )

    base = (
        base_scoring_projection(
            offense,
            defense,
            league,
        )
    )

    efficiency = (
        efficiency_adjustment(
            offense,
            defense,
            league,
        )
    )

    matchup_adj = (
        matchup_adjustment(
            matchup
        )
    )

    home_adjustment = (
        HOME_FIELD_POINTS / 2
        if home
        else -HOME_FIELD_POINTS / 2
    )

    injury_context = (
        injury_context
        or {}
    )

    injury_scoring_factor = clamp(
        f(
            injury_context.get(
                "scoring_factor"
            ),
            1.0,
        ),
        0.78,
        1.18,
    )

    pre_injury_projection = (
        base
        + efficiency
        + matchup_adj
        + home_adjustment
    )

    post_injury_projection = (
        pre_injury_projection
        * injury_scoring_factor
    )

    weather_context = (
        weather_context
        or {}
    )

    weather_available = bool(
        weather_context.get(
            "available",
            False,
        )
    )

    weather_factors = (
        weather_context.get(
            "context",
            {},
        )
        if weather_available
        else {}
    )

    weather_scoring_factor = clamp(
        f(
            weather_factors.get(
                "scoring_factor"
            ),
            1.0,
        ),
        0.88,
        1.05,
    )

    projection = (
        post_injury_projection
        * weather_scoring_factor
    )

    projection = clamp(
        projection,
        MIN_TEAM_POINTS,
        MAX_TEAM_POINTS,
    )

    return {
        "projected_points": round(
            projection,
            1,
        ),

        "components": {
            "base_scoring": round(
                base,
                2,
            ),

            "efficiency_adjustment": round(
                efficiency,
                2,
            ),

            "matchup_adjustment": round(
                matchup_adj,
                2,
            ),

            "home_field_adjustment": round(
                home_adjustment,
                2,
            ),

            "pre_injury_projection": round(
                pre_injury_projection,
                2,
            ),

            "injury_scoring_factor": round(
                injury_scoring_factor,
                3,
            ),

            "injury_adjustment_points": round(
                post_injury_projection
                - pre_injury_projection,
                2,
            ),

            "post_injury_projection": round(
                post_injury_projection,
                2,
            ),

            "weather_scoring_factor": round(
                weather_scoring_factor,
                3,
            ),

            "weather_adjustment_points": round(
                projection
                - post_injury_projection,
                2,
            ),
        },

        "injury_context": {
            "scoring_factor": round(
                injury_scoring_factor,
                3,
            ),

            "passing_factor": round(
                f(
                    injury_context.get(
                        "passing_factor"
                    ),
                    1.0,
                ),
                3,
            ),

            "rushing_factor": round(
                f(
                    injury_context.get(
                        "rushing_factor"
                    ),
                    1.0,
                ),
                3,
            ),

            "key_absences": (
                injury_context.get(
                    "key_absences",
                    [],
                )
            ),
        },

        "weather_context": {
            "available": (
                weather_available
            ),

            "roof": (
                weather_context.get(
                    "roof"
                )
            ),

            "stadium": (
                weather_context.get(
                    "stadium"
                )
            ),

            "weather": (
                weather_context.get(
                    "weather",
                    {},
                )
            ),

            "classification": (
                weather_factors.get(
                    "classification",
                    "NEUTRAL",
                )
            ),

            "severity_score": round(
                f(
                    weather_factors.get(
                        "severity_score"
                    )
                ),
                2,
            ),

            "scoring_factor": round(
                weather_scoring_factor,
                3,
            ),

            "passing_factor": round(
                f(
                    weather_factors.get(
                        "passing_factor"
                    ),
                    1.0,
                ),
                3,
            ),

            "rushing_factor": round(
                f(
                    weather_factors.get(
                        "rushing_factor"
                    ),
                    1.0,
                ),
                3,
            ),

            "kicking_factor": round(
                f(
                    weather_factors.get(
                        "kicking_factor"
                    ),
                    1.0,
                ),
                3,
            ),
        },

        "matchup_rating": round(
            f(
                matchup.get(
                    "rating"
                )
            ),
            1,
        ),

        "matchup_label": (
            matchup.get(
                "rating_label"
            )
            or "Neutral"
        ),

        "passing_matchup": {
            "rating": round(
                f(
                    nested(
                        matchup,
                        "passing",
                        "rating",
                    )
                ),
                1,
            ),

            "label": (
                nested(
                    matchup,
                    "passing",
                    "rating_label",
                    default="Neutral",
                )
            ),
        },

        "rushing_matchup": {
            "rating": round(
                f(
                    nested(
                        matchup,
                        "rushing",
                        "rating",
                    )
                ),
                1,
            ),

            "label": (
                nested(
                    matchup,
                    "rushing",
                    "rating_label",
                    default="Neutral",
                )
            ),
        },
    }

# =========================================================
# WIN PROBABILITY
# =========================================================

def calculate_win_probability(
    margin: float,
):
    """
    Converts expected point differential
    into an approximate win probability.

    This is independent of sportsbook odds.
    """

    scale = 6.5

    probability = (
        1.0
        / (
            1.0
            + math.exp(
                -margin / scale
            )
        )
    )

    return clamp(
        probability,
        0.01,
        0.99,
    )


# =========================================================
# CONFIDENCE
# =========================================================

def calculate_projection_confidence(
    away_projection: dict[str, Any],
    home_projection: dict[str, Any],
):
    away_matchup = abs(
        f(
            away_projection.get(
                "matchup_rating"
            )
        )
    )

    home_matchup = abs(
        f(
            home_projection.get(
                "matchup_rating"
            )
        )
    )

    matchup_strength = (
        (
            away_matchup
            + home_matchup
        )
        / 2
    )

    confidence = (
        50
        + matchup_strength * 0.35
    )

    return round(
        clamp(
            confidence,
            45,
            85,
        ),
        1,
    )


# =========================================================
# GAME PROJECTION
# =========================================================

def project_game(
    game: dict[str, Any],
    team_lookup: dict[
        str,
        dict[str, Any]
    ],
    matchup_lookup: dict[
        tuple[str, str],
        dict[str, Any]
    ],
    injury_lookup: dict[
        tuple[str, str],
        dict[str, Any]
    ],
    weather_lookup: dict[
        tuple[str, str],
        dict[str, Any]
    ],
    league: dict[str, float],
):
    away_team = normalize_team(
        game.get(
            "away_team"
        )
        or game.get(
            "away"
        )
    )

    home_team = normalize_team(
        game.get(
            "home_team"
        )
        or game.get(
            "home"
        )
    )

    matchup_game = (
        matchup_lookup.get(
            (
                away_team,
                home_team,
            ),
            {},
        )
    )

    injury_game = (
        injury_lookup.get(
            (
                away_team,
                home_team,
            ),
            {},
        )
    )

    weather_game = (
    weather_lookup.get(
        (
            away_team,
            home_team,
        ),
        {},
    )
)

    away_injury = (
        injury_game.get(
            "away",
            {},
        )
    )

    home_injury = (
        injury_game.get(
            "home",
            {},
        )
    )

    away_matchup = (
        matchup_game.get(
            "away",
            {},
        )
    )

    home_matchup = (
        matchup_game.get(
            "home",
            {},
        )
    )

    away_projection = (
        project_team_points(
            away_team,
            home_team,
            team_lookup,
            away_matchup,
            league,
            home=False,
            injury_context=away_injury,
            weather_context=weather_game,
        )
    )

    home_projection = (
        project_team_points(
            home_team,
            away_team,
            team_lookup,
            home_matchup,
            league,
            home=True,
            injury_context=home_injury,
            weather_context=weather_game,
        )
    )

    away_points = f(
        away_projection[
            "projected_points"
        ]
    )

    home_points = f(
        home_projection[
            "projected_points"
        ]
    )

    projected_total = (
        away_points
        + home_points
    )

    projected_total = clamp(
        projected_total,
        MIN_GAME_TOTAL,
        MAX_GAME_TOTAL,
    )

    # Positive margin = home team favored.
    expected_margin = (
        home_points
        - away_points
    )

    home_win_probability = (
        calculate_win_probability(
            expected_margin
        )
    )

    away_win_probability = (
        1
        - home_win_probability
    )

    if expected_margin > 0.25:
        projected_winner = (
            home_team
        )

    elif expected_margin < -0.25:
        projected_winner = (
            away_team
        )

    else:
        projected_winner = (
            "EVEN"
        )

    game_id = (
        game.get(
            "game_id"
        )
        or game.get(
            "id"
        )
        or game.get(
            "espn_id"
        )
        or ""
    )

    return {
        "game_id": (
            game_id
        ),

        "away_team": (
            away_team
        ),

        "home_team": (
            home_team
        ),

        "away_projection": (
            away_projection
        ),

        "home_projection": (
            home_projection
        ),

        "projected_score": {
            "away": round(
                away_points,
                1,
            ),

            "home": round(
                home_points,
                1,
            ),
        },

        "projected_total": round(
            projected_total,
            1,
        ),

        "expected_margin": round(
            expected_margin,
            1,
        ),

        "projected_winner": (
            projected_winner
        ),

        "win_probability": {
            "away": round(
                away_win_probability
                * 100,
                1,
            ),

            "home": round(
                home_win_probability
                * 100,
                1,
            ),
        },

        "projection_confidence": (
            calculate_projection_confidence(
                away_projection,
                home_projection,
            )
        ),

        "injury_context": {
            "away": away_injury,
            "home": home_injury,
        },

        "weather_context": (
            weather_game
        ),

        "model": {
            "uses_sportsbook_lines": False,

            "description": (
                "Independent Alpha Wagerz "
                "NFL game projection"
            ),
        },
    }


# =========================================================
# BUILD PROJECTION FILE
# =========================================================

def build_projection_file(
    slate_file: Path,
    matchup_file: Path,
    injury_file: Path,
    weather_file: Path,
    output_file: Path,
    web_output_file: Path,
    team_lookup: dict[
        str,
        dict[str, Any]
    ],
    league: dict[str, float],
):
    slate_payload = load_json(
        slate_file,
        default={},
    )

    matchup_payload = load_json(
        matchup_file,
        default={},
    )

    injury_payload = load_json(
        injury_file,
        default={},
    )

    weather_payload = load_json(
        weather_file,
        default={},
    )

    games = (
        slate_payload
        if isinstance(
            slate_payload,
            list,
        )
        else slate_payload.get(
            "games",
            [],
        )
    )

    matchup_lookup = (
        build_matchup_lookup(
            matchup_payload
        )
    )

    injury_lookup = (
        build_injury_lookup(
            injury_payload
        )
    )

    weather_lookup = (
        build_weather_lookup(
        weather_payload
        )
    )

    projections = []

    for game in games:
        if not isinstance(
            game,
            dict,
        ):
            continue

        away_team = normalize_team(
            game.get(
                "away_team"
            )
            or game.get(
                "away"
            )
        )

        home_team = normalize_team(
            game.get(
                "home_team"
            )
            or game.get(
                "home"
            )
        )

        if (
            not away_team
            or not home_team
        ):
            continue

        if (
            away_team
            not in team_lookup
        ):
            print(
                f"   ⚠️ Missing metrics "
                f"for {away_team}"
            )

        if (
            home_team
            not in team_lookup
        ):
            print(
                f"   ⚠️ Missing metrics "
                f"for {home_team}"
            )

        projection = (
            project_game(
                game,
                team_lookup,
                matchup_lookup,
                injury_lookup,
                weather_lookup,
                league,
            )
        )

        projections.append(
            projection
        )

        # Attach projection directly
        # to slate for downstream
        # recommendation models.

        game[
            "alpha_projection"
        ] = projection

    payload = {
        "games": (
            projections
        ),

        "league_baselines": (
            league
        ),

        "model": {
            "name": (
                "Alpha Wagerz "
                "NFL Projection Model"
            ),

            "version": (
                "1.0"
            ),

            "sportsbook_independent": (
                True
            ),
        },
    }

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    web_output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(
        payload,
        output_file,
    )

    save_json(
        payload,
        web_output_file,
    )

    # Save enriched slate too.
    save_json(
        slate_payload,
        slate_file,
    )

    print(
        f"   ✅ {len(projections)} "
        f"game projections"
    )

    print(
        f"      {output_file}"
    )

    print(
        f"      {web_output_file}"
    )

    return payload


# =========================================================
# MAIN
# =========================================================

def build_nfl_game_projections():
    print(
        "\n🏈 BUILDING NFL "
        "GAME PROJECTIONS\n"
    )

    team_payload = load_json(
        TEAM_METRICS_FILE,
        default=[],
    )

    team_lookup = (
        build_team_lookup(
            team_payload
        )
    )

    if not team_lookup:
        raise RuntimeError(
            "No NFL team metrics found. "
            "Run model.nfl.team_metrics first."
        )

    print(
        f"   Team profiles: "
        f"{len(team_lookup)}"
    )

    league = (
        calculate_league_baselines(
            team_lookup
        )
    )

    print(
        f"   League scoring baseline: "
        f"{league['points_per_game']:.2f}"
    )

    if not SLATE_FILE.exists():
        raise RuntimeError(
            f"NFL slate not found: "
            f"{SLATE_FILE}"
        )

    if not MATCHUP_METRICS_FILE.exists():
        raise RuntimeError(
            "NFL matchup metrics not found. "
            "Run model.nfl.matchup_metrics first."
        )

    if not INJURY_CONTEXT_FILE.exists():
        raise RuntimeError(
            "NFL injury context not found. "
            "Run model.nfl.injury_context first."
        )

    if not WEATHER_FILE.exists():
        raise RuntimeError(
            "NFL weather context not found. "
            "Run providers.nfl.nfl_weather first."
        )

    print(
        "\n   Current slate"
    )

    build_projection_file(
        SLATE_FILE,
        MATCHUP_METRICS_FILE,
        INJURY_CONTEXT_FILE,
        WEATHER_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
        team_lookup,
        league,
    )

    if (
        NEXT_SLATE_FILE.exists()
        and
        NEXT_MATCHUP_METRICS_FILE.exists()
        and
        NEXT_INJURY_CONTEXT_FILE.exists()
        and
        NEXT_WEATHER_FILE.exists()
    ):
        print(
            "\n   Next slate"
        )

        build_projection_file(
            NEXT_SLATE_FILE,
            NEXT_MATCHUP_METRICS_FILE,
            NEXT_INJURY_CONTEXT_FILE,
            NEXT_WEATHER_FILE,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
            team_lookup,
            league,
        )

    print(
        "\n✅ NFL GAME "
        "PROJECTIONS COMPLETE\n"
    )


if __name__ == "__main__":
    build_nfl_game_projections()

