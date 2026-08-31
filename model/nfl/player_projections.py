from __future__ import annotations

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

PLAYER_METRICS_FILE = (
    NFL_DIR
    / "player_metrics.json"
)

GAME_PROJECTIONS_FILE = (
    NFL_DIR
    / "game_projections.json"
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
    / "player_projections.json"
)

WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "player_projections.json"
)

NEXT_GAME_PROJECTIONS_FILE = (
    NFL_DIR
    / "next"
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
    / "player_projections.json"
)

NEXT_WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "next"
    / "player_projections.json"
)


# =========================================================
# SETTINGS
# =========================================================

SUPPORTED_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
}

MIN_VOLUME_FACTOR = 0.70
MAX_VOLUME_FACTOR = 1.35

MIN_EFFICIENCY_FACTOR = 0.75
MAX_EFFICIENCY_FACTOR = 1.30

MIN_TEAM_ENVIRONMENT_FACTOR = 0.75
MAX_TEAM_ENVIRONMENT_FACTOR = 1.30

LEAGUE_TEAM_POINTS = 22.5


# =========================================================
# HELPERS
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

        return float(
            value
        )

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


def normalize_position(
    value: Any,
) -> str:
    position = clean_text(
        value
    ).upper()

    aliases = {
        "HB": "RB",
        "FB": "RB",
    }

    return aliases.get(
        position,
        position,
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


def safe_divide(
    numerator: Any,
    denominator: Any,
    default: float = 0.0,
) -> float:
    denominator_value = f(
        denominator
    )

    if denominator_value == 0:
        return default

    return (
        f(numerator)
        / denominator_value
    )


def round_stat(
    value: Any,
    digits: int = 1,
):
    return round(
        f(value),
        digits,
    )


# =========================================================
# LOADERS
# =========================================================

def extract_list(
    payload: Any,
    *keys: str,
):
    if isinstance(
        payload,
        list,
    ):
        return payload

    if isinstance(
        payload,
        dict,
    ):
        for key in keys:
            rows = payload.get(
                key
            )

            if isinstance(
                rows,
                list,
            ):
                return rows

    return []


def build_player_lookup(
    payload: Any,
):
    rows = extract_list(
        payload,
        "players",
        "player_metrics",
    )

    lookup = {}

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        player_id = clean_text(
            row.get(
                "player_id"
            )
        )

        if player_id:
            lookup[
                player_id
            ] = row

    return lookup


def build_game_projection_lookup(
    payload: Any,
):
    games = extract_list(
        payload,
        "games",
    )

    lookup = {}

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


def build_matchup_lookup(
    payload: Any,
):
    games = extract_list(
        payload,
        "games",
    )

    lookup = {}

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
# INJURY CONTEXT
# =========================================================

def build_injury_lookup(
    payload: Any,
):
    games = extract_list(
        payload,
        "games",
    )

    lookup = {}

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

        if away and home:
            lookup[
                (
                    away,
                    home,
                )
            ] = game

    return lookup


# =========================================================
# WEATHER CONTEXT
# =========================================================

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


def get_team_injury_context(
    team: str,
    game_injury: dict[str, Any],
):
    away_team = normalize_team(
        game_injury.get(
            "away_team"
        )
    )

    home_team = normalize_team(
        game_injury.get(
            "home_team"
        )
    )

    if team == away_team:
        return game_injury.get(
            "away",
            {},
        )

    if team == home_team:
        return game_injury.get(
            "home",
            {},
        )

    return {}


def player_availability_factor(
    player_id: str,
    player_name: str,
    team_injury: dict[str, Any],
):
    team_context = (
        team_injury.get(
            "team_context",
            {},
        )
        if isinstance(
            team_injury,
            dict,
        )
        else {}
    )

    injuries = team_context.get(
        "injuries",
        [],
    )

    if not isinstance(
        injuries,
        list,
    ):
        injuries = []

    matched = None

    for injury in injuries:
        if not isinstance(
            injury,
            dict,
        ):
            continue

        injury_id = clean_text(
            injury.get(
                "player_id"
            )
        )

        injury_name = clean_text(
            injury.get(
                "player"
            )
        )

        if (
            player_id
            and injury_id
            and player_id == injury_id
        ):
            matched = injury
            break

        if (
            player_name
            and injury_name
            and player_name.lower()
            == injury_name.lower()
        ):
            matched = injury
            break

    if not matched:
        return 1.0, None

    status = clean_text(
        matched.get(
            "status"
        )
    ).upper()

    factors = {
        "OUT": 0.0,
        "IR": 0.0,
        "INJURED RESERVE": 0.0,
        "PUP": 0.0,
        "NFI": 0.0,
        "DOUBTFUL": 0.25,
        "QUESTIONABLE": 0.80,
        "LIMITED": 0.90,
        "PROBABLE": 0.98,
        "ACTIVE": 1.0,
        "FULL": 1.0,
    }

    return (
        factors.get(
            status,
            1.0,
        ),
        matched,
    )


def apply_availability_factor(
    projection: dict[str, Any],
    factor: float,
):
    if factor >= 0.999:
        return projection

    adjusted = {}

    for category, stats in (
        projection.items()
    ):
        if not isinstance(
            stats,
            dict,
        ):
            adjusted[
                category
            ] = stats
            continue

        adjusted_stats = {}

        for key, value in (
            stats.items()
        ):
            if isinstance(
                value,
                (int, float),
            ):
                adjusted_stats[
                    key
                ] = round_stat(
                    f(value) * factor,
                    2
                    if key in {
                        "touchdowns",
                        "interceptions",
                    }
                    else 1,
                )
            else:
                adjusted_stats[
                    key
                ] = value

        adjusted[
            category
        ] = adjusted_stats

    return adjusted


# =========================================================
# SLATE PLAYER EXTRACTION
# =========================================================

def collect_slate_players(
    slate_payload: Any,
):
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
        if isinstance(
            slate_payload,
            dict,
        )
        else []
    )

    output = []

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

        players = game.get(
            "players",
            {}
        )

        if not isinstance(
            players,
            dict,
        ):
            continue

        for side, team, opponent in (
            (
                "away",
                away_team,
                home_team,
            ),
            (
                "home",
                home_team,
                away_team,
            ),
        ):
            rows = players.get(
                side,
                []
            )

            if not isinstance(
                rows,
                list,
            ):
                continue

            for player in rows:
                if not isinstance(
                    player,
                    dict,
                ):
                    continue

                player_id = clean_text(
                    player.get(
                        "player_id"
                    )
                    or player.get(
                        "gsis_id"
                    )
                    or player.get(
                        "id"
                    )
                )

                if not player_id:
                    continue

                output.append(
                    {
                        "player_id": (
                            player_id
                        ),

                        "player": clean_text(
                            player.get(
                                "player"
                            )
                            or player.get(
                                "player_name"
                            )
                            or player.get(
                                "name"
                            )
                        ),

                        "team": (
                            team
                        ),

                        "opponent": (
                            opponent
                        ),

                        "position": (
                            normalize_position(
                                player.get(
                                    "position"
                                )
                                or player.get(
                                    "pos"
                                )
                            )
                        ),

                        "side": (
                            side
                        ),

                        "game_id": (
                            game.get(
                                "game_id"
                            )
                            or game.get(
                                "id"
                            )
                            or ""
                        ),
                    }
                )

    return output


# =========================================================
# ENVIRONMENT
# =========================================================

def team_game_environment(
    team: str,
    opponent: str,
    game_projection: dict[str, Any],
):
    away_team = normalize_team(
        game_projection.get(
            "away_team"
        )
    )

    home_team = normalize_team(
        game_projection.get(
            "home_team"
        )
    )

    if team == away_team:
        projected_points = f(
            nested(
                game_projection,
                "projected_score",
                "away",
                default=LEAGUE_TEAM_POINTS,
            ),
            LEAGUE_TEAM_POINTS,
        )

        win_probability = f(
            nested(
                game_projection,
                "win_probability",
                "away",
                default=50,
            ),
            50,
        )

    elif team == home_team:
        projected_points = f(
            nested(
                game_projection,
                "projected_score",
                "home",
                default=LEAGUE_TEAM_POINTS,
            ),
            LEAGUE_TEAM_POINTS,
        )

        win_probability = f(
            nested(
                game_projection,
                "win_probability",
                "home",
                default=50,
            ),
            50,
        )

    else:
        projected_points = (
            LEAGUE_TEAM_POINTS
        )

        win_probability = 50.0

    scoring_factor = safe_divide(
        projected_points,
        LEAGUE_TEAM_POINTS,
        default=1.0,
    )

    scoring_factor = clamp(
        scoring_factor,
        MIN_TEAM_ENVIRONMENT_FACTOR,
        MAX_TEAM_ENVIRONMENT_FACTOR,
    )

    projected_total = f(
        game_projection.get(
            "projected_total"
        ),
        LEAGUE_TEAM_POINTS * 2,
    )

    total_factor = safe_divide(
        projected_total,
        LEAGUE_TEAM_POINTS * 2,
        default=1.0,
    )

    total_factor = clamp(
        total_factor,
        0.80,
        1.20,
    )

    return {
        "projected_team_points": round(
            projected_points,
            1,
        ),

        "projected_game_total": round(
            projected_total,
            1,
        ),

        "win_probability": round(
            win_probability,
            1,
        ),

        "scoring_factor": round(
            scoring_factor,
            3,
        ),

        "total_factor": round(
            total_factor,
            3,
        ),
    }


# =========================================================
# MATCHUP FACTORS
# =========================================================

def rating_to_factor(
    rating: Any,
    scale: float,
):
    value = f(
        rating
    )

    factor = (
        1.0
        + value * scale
    )

    return clamp(
        factor,
        MIN_EFFICIENCY_FACTOR,
        MAX_EFFICIENCY_FACTOR,
    )


def get_team_matchup(
    team: str,
    game_matchup: dict[str, Any],
):
    away_team = normalize_team(
        game_matchup.get(
            "away_team"
        )
    )

    home_team = normalize_team(
        game_matchup.get(
            "home_team"
        )
    )

    if team == away_team:
        return (
            game_matchup.get(
                "away",
                {},
            )
        )

    if team == home_team:
        return (
            game_matchup.get(
                "home",
                {},
            )
        )

    return {}


def build_matchup_factors(
    team: str,
    game_matchup: dict[str, Any],
):
    matchup = get_team_matchup(
        team,
        game_matchup,
    )

    overall_rating = f(
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

    return {
        "overall_rating": round(
            overall_rating,
            1,
        ),

        "passing_rating": round(
            passing_rating,
            1,
        ),

        "rushing_rating": round(
            rushing_rating,
            1,
        ),

        "overall_factor": round(
            rating_to_factor(
                overall_rating,
                0.003,
            ),
            3,
        ),

        "passing_factor": round(
            rating_to_factor(
                passing_rating,
                0.004,
            ),
            3,
        ),

        "rushing_factor": round(
            rating_to_factor(
                rushing_rating,
                0.004,
            ),
            3,
        ),
    }


# =========================================================
# QB PROJECTION
# =========================================================

def project_qb(
    player: dict[str, Any],
    environment: dict[str, Any],
    matchup: dict[str, Any],
):
    passing = player.get(
        "passing",
        {},
    )

    rushing = player.get(
        "rushing",
        {},
    )

    attempts_pg = f(
        passing.get(
            "attempts_per_game"
        )
    )

    completions_pg = f(
        passing.get(
            "completions_per_game"
        )
    )

    pass_yards_pg = f(
        passing.get(
            "yards_per_game"
        )
    )

    pass_tds_pg = f(
        passing.get(
            "touchdowns_per_game"
        )
    )

    interceptions_pg = f(
        passing.get(
            "interceptions_per_game"
        )
    )

    rush_carries_pg = f(
        rushing.get(
            "carries_per_game"
        )
    )

    rush_yards_pg = f(
        rushing.get(
            "yards_per_game"
        )
    )

    rush_tds_pg = f(
        rushing.get(
            "touchdowns_per_game"
        )
    )

    passing_factor = f(
        matchup.get(
            "passing_factor"
        ),
        1.0,
    )

    rushing_factor = f(
        matchup.get(
            "rushing_factor"
        ),
        1.0,
    )

    scoring_factor = f(
        environment.get(
            "scoring_factor"
        ),
        1.0,
    )

    total_factor = f(
        environment.get(
            "total_factor"
        ),
        1.0,
    )

    win_probability = f(
        environment.get(
            "win_probability"
        ),
        50.0,
    )

    # Slightly more pass volume when projected
    # to be behind, less when strongly favored.
    pass_script_factor = (
        1.0
        + (
            50.0
            - win_probability
        )
        * 0.0025
    )

    pass_script_factor = clamp(
        pass_script_factor,
        0.90,
        1.12,
    )

    projected_attempts = (
        attempts_pg
        * pass_script_factor
        * total_factor
    )

    completion_rate = safe_divide(
        completions_pg,
        attempts_pg,
        default=f(
            passing.get(
                "completion_rate"
            )
        )
        / 100,
    )

    completion_rate = clamp(
        completion_rate
        * (
            0.985
            + (
                passing_factor
                - 1.0
            )
            * 0.30
        ),
        0.50,
        0.78,
    )

    projected_completions = (
        projected_attempts
        * completion_rate
    )

    projected_pass_yards = (
        pass_yards_pg
        * pass_script_factor
        * passing_factor
        * total_factor
    )

    projected_pass_tds = (
        pass_tds_pg
        * passing_factor
        * scoring_factor
    )

    # Favorable passing matchups do not
    # automatically raise INT projection.
    interception_factor = clamp(
        2.0 - passing_factor,
        0.75,
        1.25,
    )

    projected_interceptions = (
        interceptions_pg
        * pass_script_factor
        * interception_factor
    )

    rush_script_factor = (
        1.0
        + (
            win_probability
            - 50.0
        )
        * 0.001
    )

    rush_script_factor = clamp(
        rush_script_factor,
        0.95,
        1.05,
    )

    projected_rush_attempts = (
        rush_carries_pg
        * rush_script_factor
    )

    projected_rush_yards = (
        rush_yards_pg
        * rushing_factor
    )

    projected_rush_tds = (
        rush_tds_pg
        * rushing_factor
        * scoring_factor
    )

    return {
        "passing": {
            "attempts": round_stat(
                projected_attempts,
            ),

            "completions": round_stat(
                projected_completions,
            ),

            "yards": round_stat(
                projected_pass_yards,
            ),

            "touchdowns": round_stat(
                projected_pass_tds,
                2,
            ),

            "interceptions": round_stat(
                projected_interceptions,
                2,
            ),
        },

        "rushing": {
            "carries": round_stat(
                projected_rush_attempts,
            ),

            "yards": round_stat(
                projected_rush_yards,
            ),

            "touchdowns": round_stat(
                projected_rush_tds,
                2,
            ),
        },
    }


# =========================================================
# RB PROJECTION
# =========================================================

def project_rb(
    player: dict[str, Any],
    environment: dict[str, Any],
    matchup: dict[str, Any],
):
    rushing = player.get(
        "rushing",
        {},
    )

    receiving = player.get(
        "receiving",
        {},
    )

    rush_factor = f(
        matchup.get(
            "rushing_factor"
        ),
        1.0,
    )

    pass_factor = f(
        matchup.get(
            "passing_factor"
        ),
        1.0,
    )

    scoring_factor = f(
        environment.get(
            "scoring_factor"
        ),
        1.0,
    )

    win_probability = f(
        environment.get(
            "win_probability"
        ),
        50,
    )

    carries_pg = f(
        rushing.get(
            "carries_per_game"
        )
    )

    rush_yards_pg = f(
        rushing.get(
            "yards_per_game"
        )
    )

    rush_tds_pg = f(
        rushing.get(
            "touchdowns_per_game"
        )
    )

    targets_pg = f(
        receiving.get(
            "targets_per_game"
        )
    )

    receptions_pg = f(
        receiving.get(
            "receptions_per_game"
        )
    )

    receiving_yards_pg = f(
        receiving.get(
            "yards_per_game"
        )
    )

    receiving_tds_pg = f(
        receiving.get(
            "touchdowns_per_game"
        )
    )

    rushing_script_factor = (
        1.0
        + (
            win_probability
            - 50
        )
        * 0.004
    )

    rushing_script_factor = clamp(
        rushing_script_factor,
        0.85,
        1.18,
    )

    receiving_script_factor = (
        1.0
        + (
            50
            - win_probability
        )
        * 0.003
    )

    receiving_script_factor = clamp(
        receiving_script_factor,
        0.90,
        1.15,
    )

    projected_carries = (
        carries_pg
        * rushing_script_factor
    )

    projected_rush_yards = (
        rush_yards_pg
        * rushing_script_factor
        * rush_factor
    )

    projected_rush_tds = (
        rush_tds_pg
        * rush_factor
        * scoring_factor
    )

    projected_targets = (
        targets_pg
        * receiving_script_factor
    )

    catch_rate = safe_divide(
        receptions_pg,
        targets_pg,
        default=f(
            receiving.get(
                "catch_rate"
            )
        )
        / 100,
    )

    projected_receptions = (
        projected_targets
        * clamp(
            catch_rate,
            0.45,
            0.90,
        )
    )

    projected_receiving_yards = (
        receiving_yards_pg
        * receiving_script_factor
        * pass_factor
    )

    projected_receiving_tds = (
        receiving_tds_pg
        * pass_factor
        * scoring_factor
    )

    return {
        "rushing": {
            "carries": round_stat(
                projected_carries,
            ),

            "yards": round_stat(
                projected_rush_yards,
            ),

            "touchdowns": round_stat(
                projected_rush_tds,
                2,
            ),
        },

        "receiving": {
            "targets": round_stat(
                projected_targets,
            ),

            "receptions": round_stat(
                projected_receptions,
            ),

            "yards": round_stat(
                projected_receiving_yards,
            ),

            "touchdowns": round_stat(
                projected_receiving_tds,
                2,
            ),
        },
    }


# =========================================================
# WR / TE PROJECTION
# =========================================================

def project_receiver(
    player: dict[str, Any],
    environment: dict[str, Any],
    matchup: dict[str, Any],
):
    receiving = player.get(
        "receiving",
        {},
    )

    pass_factor = f(
        matchup.get(
            "passing_factor"
        ),
        1.0,
    )

    scoring_factor = f(
        environment.get(
            "scoring_factor"
        ),
        1.0,
    )

    total_factor = f(
        environment.get(
            "total_factor"
        ),
        1.0,
    )

    win_probability = f(
        environment.get(
            "win_probability"
        ),
        50,
    )

    targets_pg = f(
        receiving.get(
            "targets_per_game"
        )
    )

    receptions_pg = f(
        receiving.get(
            "receptions_per_game"
        )
    )

    yards_pg = f(
        receiving.get(
            "yards_per_game"
        )
    )

    touchdowns_pg = f(
        receiving.get(
            "touchdowns_per_game"
        )
    )

    script_factor = (
        1.0
        + (
            50
            - win_probability
        )
        * 0.0025
    )

    script_factor = clamp(
        script_factor,
        0.90,
        1.12,
    )

    projected_targets = (
        targets_pg
        * script_factor
        * total_factor
    )

    catch_rate = safe_divide(
        receptions_pg,
        targets_pg,
        default=f(
            receiving.get(
                "catch_rate"
            )
        )
        / 100,
    )

    catch_rate = clamp(
        catch_rate
        * (
            0.99
            + (
                pass_factor
                - 1.0
            )
            * 0.20
        ),
        0.40,
        0.90,
    )

    projected_receptions = (
        projected_targets
        * catch_rate
    )

    projected_yards = (
        yards_pg
        * script_factor
        * pass_factor
        * total_factor
    )

    projected_touchdowns = (
        touchdowns_pg
        * pass_factor
        * scoring_factor
    )

    return {
        "receiving": {
            "targets": round_stat(
                projected_targets,
            ),

            "receptions": round_stat(
                projected_receptions,
            ),

            "yards": round_stat(
                projected_yards,
            ),

            "touchdowns": round_stat(
                projected_touchdowns,
                2,
            ),
        },
    }


# =========================================================
# FANTASY PROJECTION
# =========================================================

def calculate_fantasy(
    position: str,
    projection: dict[str, Any],
):
    passing = projection.get(
        "passing",
        {},
    )

    rushing = projection.get(
        "rushing",
        {},
    )

    receiving = projection.get(
        "receiving",
        {},
    )

    standard = 0.0

    standard += (
        f(
            passing.get(
                "yards"
            )
        )
        / 25.0
    )

    standard += (
        f(
            passing.get(
                "touchdowns"
            )
        )
        * 4.0
    )

    standard -= (
        f(
            passing.get(
                "interceptions"
            )
        )
        * 2.0
    )

    standard += (
        f(
            rushing.get(
                "yards"
            )
        )
        / 10.0
    )

    standard += (
        f(
            rushing.get(
                "touchdowns"
            )
        )
        * 6.0
    )

    standard += (
        f(
            receiving.get(
                "yards"
            )
        )
        / 10.0
    )

    standard += (
        f(
            receiving.get(
                "touchdowns"
            )
        )
        * 6.0
    )

    ppr = (
        standard
        + f(
            receiving.get(
                "receptions"
            )
        )
    )

    return {
        "standard": round(
            standard,
            2,
        ),

        "ppr": round(
            ppr,
            2,
        ),
    }


# =========================================================
# PLAYER PROJECTION
# =========================================================

def project_player(
    slate_player: dict[str, Any],
    player_metrics: dict[str, Any],
    game_projection: dict[str, Any],
    game_matchup: dict[str, Any],
    game_injury: dict[str, Any],
    game_weather: dict[str, Any],
):
    team = normalize_team(
        slate_player.get(
            "team"
        )
    )

    opponent = normalize_team(
        slate_player.get(
            "opponent"
        )
    )

    position = normalize_position(
        player_metrics.get(
            "position"
        )
        or slate_player.get(
            "position"
        )
    )

    environment = (
        team_game_environment(
            team,
            opponent,
            game_projection,
        )
    )

    matchup = (
        build_matchup_factors(
            team,
            game_matchup,
        )
    )

    injury_context = (
        get_team_injury_context(
            team,
            game_injury,
        )
    )

    injury_passing_factor = clamp(
        f(
            injury_context.get(
                "passing_factor"
            ),
            1.0,
        ),
        0.75,
        1.20,
    )

    injury_rushing_factor = clamp(
        f(
            injury_context.get(
                "rushing_factor"
            ),
            1.0,
        ),
        0.78,
        1.18,
    )

    game_weather = (
        game_weather
        or {}
    )

    weather_available = bool(
        game_weather.get(
            "available",
            False,
        )
    )

    weather_context = (
        game_weather.get(
            "context",
            {},
        )
        if weather_available
        else {}
    )

    weather_passing_factor = clamp(
        f(
            weather_context.get(
                "passing_factor"
            ),
            1.0,
        ),
        0.75,
        1.10,
    )

    weather_rushing_factor = clamp(
        f(
            weather_context.get(
                "rushing_factor"
            ),
            1.0,
        ),
        0.90,
        1.15,
    )

    matchup[
        "passing_factor"
    ] = round(
        clamp(
            f(
                matchup.get(
                    "passing_factor"
                ),
                1.0,
            )
            * injury_passing_factor
            * weather_passing_factor,
            MIN_EFFICIENCY_FACTOR,
            MAX_EFFICIENCY_FACTOR,
        ),
        3,
    )

    matchup[
        "rushing_factor"
    ] = round(
        clamp(
            f(
                matchup.get(
                    "rushing_factor"
                ),
                1.0,
            )
            * injury_rushing_factor
            * weather_rushing_factor,
            MIN_EFFICIENCY_FACTOR,
            MAX_EFFICIENCY_FACTOR,
        ),
        3,
    )

    availability_factor, player_injury = (
        player_availability_factor(
            clean_text(
                player_metrics.get(
                    "player_id"
                )
            ),
            clean_text(
                player_metrics.get(
                    "player"
                )
                or slate_player.get(
                    "player"
                )
            ),
            injury_context,
        )
    )

    if position == "QB":
        projection = project_qb(
            player_metrics,
            environment,
            matchup,
        )

    elif position == "RB":
        projection = project_rb(
            player_metrics,
            environment,
            matchup,
        )

    elif position in {
        "WR",
        "TE",
    }:
        projection = project_receiver(
            player_metrics,
            environment,
            matchup,
        )

    else:
        return None

    projection = (
        apply_availability_factor(
            projection,
            availability_factor,
        )
    )

    fantasy = (
        calculate_fantasy(
            position,
            projection,
        )
    )

    return {
        "player_id": (
            player_metrics.get(
                "player_id"
            )
        ),

        "player": (
            player_metrics.get(
                "player"
            )
            or slate_player.get(
                "player"
            )
        ),

        "team": (
            team
        ),

        "opponent": (
            opponent
        ),

        "position": (
            position
        ),

        "game_id": (
            slate_player.get(
                "game_id"
            )
        ),

        "projection": (
            projection
        ),

        "fantasy": (
            fantasy
        ),

        "environment": (
            environment
        ),

        "matchup": (
            matchup
        ),

        "injury_context": {
            "team": injury_context,

            "passing_factor": round(
                injury_passing_factor,
                3,
            ),

            "rushing_factor": round(
                injury_rushing_factor,
                3,
            ),

            "availability_factor": round(
                availability_factor,
                3,
            ),

            "player_injury": (
                player_injury
            ),
        },

        "weather_context": {
            "available": (
                weather_available
            ),

            "roof": (
                game_weather.get(
                    "roof"
                )
            ),

            "stadium": (
                game_weather.get(
                    "stadium"
                )
            ),

            "weather": (
                game_weather.get(
                    "weather",
                    {},
                )
            ),

            "classification": (
                weather_context.get(
                    "classification",
                    "NEUTRAL",
                )
            ),

            "severity_score": round(
                f(
                    weather_context.get(
                        "severity_score"
                    )
                ),
                2,
            ),

            "passing_factor": round(
                weather_passing_factor,
                3,
            ),

            "rushing_factor": round(
                weather_rushing_factor,
                3,
            ),

            "kicking_factor": round(
                f(
                    weather_context.get(
                        "kicking_factor"
                    ),
                    1.0,
                ),
                3,
            ),
        },

        "sample": (
            player_metrics.get(
                "sample",
                {},
            )
        ),

        "baseline": {
            "games": (
                player_metrics.get(
                    "games"
                )
            ),

            "passing": (
                player_metrics.get(
                    "passing",
                    {},
                )
            ),

            "rushing": (
                player_metrics.get(
                    "rushing",
                    {},
                )
            ),

            "receiving": (
                player_metrics.get(
                    "receiving",
                    {},
                )
            ),
        },

        "model": {
            "sportsbook_independent": (
                True
            ),
        },
    }


# =========================================================
# BUILD ONE SLATE
# =========================================================

def build_projection_file(
    slate_file: Path,
    game_projection_file: Path,
    matchup_file: Path,
    injury_file: Path,
    weather_file: Path,
    output_file: Path,
    web_output_file: Path,
    player_lookup: dict[
        str,
        dict[str, Any]
    ],
):
    slate_payload = load_json(
        slate_file,
        default={},
    )

    game_projection_payload = load_json(
        game_projection_file,
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

    slate_players = (
        collect_slate_players(
            slate_payload
        )
    )

    game_projection_lookup = (
        build_game_projection_lookup(
            game_projection_payload
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

    missing_metrics = 0
    missing_game = 0
    missing_matchup = 0
    missing_injury = 0
    missing_weather = 0

    position_counts = {
        "QB": 0,
        "RB": 0,
        "WR": 0,
        "TE": 0,
    }

    for slate_player in (
        slate_players
    ):
        player_id = clean_text(
            slate_player.get(
                "player_id"
            )
        )

        metrics = (
            player_lookup.get(
                player_id
            )
        )

        if not metrics:
            missing_metrics += 1
            continue

        position = normalize_position(
            metrics.get(
                "position"
            )
        )

        if position not in (
            SUPPORTED_POSITIONS
        ):
            continue

        team = normalize_team(
            slate_player.get(
                "team"
            )
        )

        opponent = normalize_team(
            slate_player.get(
                "opponent"
            )
        )

        if (
            slate_player.get(
                "side"
            )
            == "away"
        ):
            game_key = (
                team,
                opponent,
            )

        else:
            game_key = (
                opponent,
                team,
            )

        game_projection = (
            game_projection_lookup.get(
                game_key
            )
        )

        if not game_projection:
            missing_game += 1
            continue

        game_matchup = (
            matchup_lookup.get(
                game_key
            )
        )

        if not game_matchup:
            missing_matchup += 1
            continue

        game_injury = (
            injury_lookup.get(
                game_key
            )
        )

        if not game_injury:
            missing_injury += 1
            game_injury = {
                "away_team": game_key[0],
                "home_team": game_key[1],
                "away": {},
                "home": {},
            }

        game_weather = (
            weather_lookup.get(
                game_key
            )
        )

        if not game_weather:
            missing_weather += 1
            game_weather = {
                "away_team": game_key[0],
                "home_team": game_key[1],
                "available": False,
                "context": {},
            }

        projection = (
            project_player(
                slate_player,
                metrics,
                game_projection,
                game_matchup,
                game_injury,
                game_weather,
            )
        )

        if not projection:
            continue

        projections.append(
            projection
        )

        position_counts[
            position
        ] += 1

    projections.sort(
        key=lambda row: (
            row.get(
                "game_id",
                "",
            ),
            row.get(
                "team",
                "",
            ),
            row.get(
                "position",
                "",
            ),
            row.get(
                "player",
                "",
            ),
        )
    )

    payload = {
        "players": (
            projections
        ),

        "counts": {
            "total": len(
                projections
            ),

            "QB": (
                position_counts[
                    "QB"
                ]
            ),

            "RB": (
                position_counts[
                    "RB"
                ]
            ),

            "WR": (
                position_counts[
                    "WR"
                ]
            ),

            "TE": (
                position_counts[
                    "TE"
                ]
            ),
        },

        "diagnostics": {
            "slate_players": (
                len(
                    slate_players
                )
            ),

            "missing_player_metrics": (
                missing_metrics
            ),

            "missing_game_projection": (
                missing_game
            ),

            "missing_matchup_metrics": (
                missing_matchup
            ),

            "missing_injury_context": (
                missing_injury
            ),

            "missing_weather_context": (
                missing_weather
            ),
        },

        "model": {
            "name": (
                "Alpha Wagerz "
                "NFL Player Projection Model"
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

    print(
        f"   ✅ {len(projections)} "
        f"player projections"
    )

    print(
        f"      QB: "
        f"{position_counts['QB']}"
    )

    print(
        f"      RB: "
        f"{position_counts['RB']}"
    )

    print(
        f"      WR: "
        f"{position_counts['WR']}"
    )

    print(
        f"      TE: "
        f"{position_counts['TE']}"
    )

    if missing_metrics:
        print(
            f"   ⚠️ Missing player "
            f"metrics: {missing_metrics}"
        )

    if missing_game:
        print(
            f"   ⚠️ Missing game "
            f"projections: {missing_game}"
        )

    if missing_matchup:
        print(
            f"   ⚠️ Missing matchup "
            f"metrics: {missing_matchup}"
        )

    if missing_injury:
        print(
            f"   ⚠️ Missing injury "
            f"context: {missing_injury}"
        )

    if missing_weather:
        print(
            f"   ⚠️ Missing weather "
            f"context: {missing_weather}"
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

def build_nfl_player_projections():
    print(
        "\n🏃 BUILDING NFL "
        "PLAYER PROJECTIONS\n"
    )

    player_payload = load_json(
        PLAYER_METRICS_FILE,
        default={},
    )

    player_lookup = (
        build_player_lookup(
            player_payload
        )
    )

    if not player_lookup:
        raise RuntimeError(
            "No NFL player metrics found. "
            "Run model.nfl.player_metrics first."
        )

    print(
        f"   Player profiles: "
        f"{len(player_lookup)}"
    )

    if not SLATE_FILE.exists():
        raise RuntimeError(
            f"NFL slate not found: "
            f"{SLATE_FILE}"
        )

    if not GAME_PROJECTIONS_FILE.exists():
        raise RuntimeError(
            "NFL game projections not found. "
            "Run model.nfl.game_projections first."
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
            "Run providers.nfl_weather first."
        )

    print(
        "\n   Current slate"
    )

    build_projection_file(
        SLATE_FILE,
        GAME_PROJECTIONS_FILE,
        MATCHUP_METRICS_FILE,
        INJURY_CONTEXT_FILE,
        WEATHER_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
        player_lookup,
    )

    if (
        NEXT_SLATE_FILE.exists()
        and
        NEXT_GAME_PROJECTIONS_FILE.exists()
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
            NEXT_GAME_PROJECTIONS_FILE,
            NEXT_MATCHUP_METRICS_FILE,
            NEXT_INJURY_CONTEXT_FILE,
            NEXT_WEATHER_FILE,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
            player_lookup,
        )

    print(
        "\n✅ NFL PLAYER "
        "PROJECTIONS COMPLETE\n"
    )

    return True


if __name__ == "__main__":
    build_nfl_player_projections()