from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


MODEL_ROOT = Path(__file__).resolve().parents[2]

NFL_DIR = MODEL_ROOT / "data" / "processed" / "nfl"

WEB_NFL_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nfl"
)

PLAYER_METRICS_FILE = NFL_DIR / "player_metrics.json"
PLAYER_PROJECTIONS_FILE = NFL_DIR / "player_projections.json"

OUTPUT_FILE = NFL_DIR / "touchdown_projections.json"
WEB_OUTPUT_FILE = WEB_NFL_DIR / "touchdown_projections.json"

NEXT_PLAYER_PROJECTIONS_FILE = (
    NFL_DIR / "next" / "player_projections.json"
)
NEXT_OUTPUT_FILE = (
    NFL_DIR / "next" / "touchdown_projections.json"
)
NEXT_WEB_OUTPUT_FILE = (
    WEB_NFL_DIR / "next" / "touchdown_projections.json"
)


SUPPORTED_POSITIONS = {"QB", "RB", "WR", "TE"}

# Number of current-season games required before the current
# scoring rate receives roughly half of the historical-rate weight.
CURRENT_RATE_STABILIZATION_GAMES = 8.0

# Blend between the player's regressed scoring history and the
# upstream single-game TD projection.
#
# The upstream projection already incorporates projected volume,
# matchup, scoring environment, injuries and weather, so those
# factors must NOT be multiplied into lambda a second time.
HISTORICAL_RATE_WEIGHT = 0.60
GAME_PROJECTION_WEIGHT = 0.40

# Protect against an extreme raw TD projection dominating the blend.
MAX_GAME_TD_PROJECTION = 1.25

# Final expected scoring-TD ceiling.
MAX_TOUCHDOWN_LAMBDA = 1.50

# A player with no demonstrated scoring history and no projected
# scoring opportunity remains at zero rather than receiving an
# arbitrary fake probability.
MIN_MEANINGFUL_LAMBDA = 0.001


def f(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_position(value: Any) -> str:
    position = clean_text(value).upper()

    aliases = {
        "HB": "RB",
        "FB": "RB",
    }

    return aliases.get(position, position)


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(minimum, min(maximum, value))


def nested(
    payload: dict[str, Any],
    *keys: str,
    default: Any = 0.0,
) -> Any:
    current: Any = payload

    for key in keys:
        if not isinstance(current, dict):
            return default

        current = current.get(key)

        if current is None:
            return default

    return current


def extract_players(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [
            row
            for row in payload
            if isinstance(row, dict)
        ]

    if isinstance(payload, dict):
        rows = payload.get("players", [])

        if isinstance(rows, list):
            return [
                row
                for row in rows
                if isinstance(row, dict)
            ]

    return []


def build_metrics_lookup(
    payload: Any,
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}

    for row in extract_players(payload):
        player_id = clean_text(row.get("player_id"))

        if player_id:
            lookup[player_id] = row

    return lookup


def scoring_rates(
    metrics: dict[str, Any],
) -> dict[str, float]:
    games = max(
        0.0,
        f(metrics.get("games")),
    )

    current_rush = max(
        0.0,
        f(
            nested(
                metrics,
                "rushing",
                "touchdowns_per_game",
            )
        ),
    )

    current_rec = max(
        0.0,
        f(
            nested(
                metrics,
                "receiving",
                "touchdowns_per_game",
            )
        ),
    )

    career_rush = max(
        0.0,
        f(
            nested(
                metrics,
                "career",
                "averages",
                "rushing_tds",
            )
        ),
    )

    career_rec = max(
        0.0,
        f(
            nested(
                metrics,
                "career",
                "averages",
                "receiving_tds",
            )
        ),
    )

    # Small current-season samples are aggressively regressed
    # toward career scoring ability.
    current_weight = (
        games
        / (
            games
            + CURRENT_RATE_STABILIZATION_GAMES
        )
        if games > 0
        else 0.0
    )

    career_weight = 1.0 - current_weight

    rush_rate = (
        current_rush * current_weight
        + career_rush * career_weight
    )

    receiving_rate = (
        current_rec * current_weight
        + career_rec * career_weight
    )

    return {
        "games": games,
        "current_weight": current_weight,
        "career_weight": career_weight,
        "current_rushing_td_rate": current_rush,
        "current_receiving_td_rate": current_rec,
        "career_rushing_td_rate": career_rush,
        "career_receiving_td_rate": career_rec,
        "rushing_td_rate": rush_rate,
        "receiving_td_rate": receiving_rate,
        "total_td_rate": rush_rate + receiving_rate,
    }


def usage_factor(
    metrics: dict[str, Any],
) -> float:
    """
    Compare current opportunity to career opportunity.

    This is deliberately bounded because TD probability should
    not explode solely because of a short-term volume spike.
    """
    current_opportunities = max(
        0.0,
        f(
            nested(
                metrics,
                "usage",
                "opportunities_per_game",
            )
        ),
    )

    career_carries = max(
        0.0,
        f(
            nested(
                metrics,
                "career",
                "averages",
                "carries",
            )
        ),
    )

    career_targets = max(
        0.0,
        f(
            nested(
                metrics,
                "career",
                "averages",
                "targets",
            )
        ),
    )

    career_opportunities = (
        career_carries
        + career_targets
    )

    if (
        current_opportunities <= 0
        or career_opportunities <= 0
    ):
        return 1.0

    raw_factor = (
        current_opportunities
        / career_opportunities
    )

    # Only part of a usage change should transfer directly into
    # scoring expectation.
    softened = (
        1.0
        + (raw_factor - 1.0) * 0.35
    )

    return clamp(
        softened,
        0.75,
        1.30,
    )


def player_availability(
    player: dict[str, Any],
) -> tuple[float, str]:
    injury_context = player.get(
        "injury_context",
        {},
    )

    if not isinstance(injury_context, dict):
        return 1.0, ""

    player_injury = injury_context.get(
        "player",
    )

    if not isinstance(player_injury, dict):
        return 1.0, ""

    status = clean_text(
        player_injury.get("status")
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
        factors.get(status, 1.0),
        status,
    )


def poisson_at_least_one(
    touchdown_lambda: float,
) -> float:
    if touchdown_lambda <= 0:
        return 0.0

    return (
        1.0
        - math.exp(-touchdown_lambda)
    )


def build_player_touchdown_projection(
    player: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any] | None:
    position = normalize_position(
        player.get("position")
    )

    if position not in SUPPORTED_POSITIONS:
        return None

    projection = player.get(
        "projection",
        {},
    )

    if not isinstance(projection, dict):
        projection = {}

    projected_rushing_tds = max(
        0.0,
        f(
            nested(
                projection,
                "rushing",
                "touchdowns",
            )
        ),
    )

    projected_receiving_tds = max(
        0.0,
        f(
            nested(
                projection,
                "receiving",
                "touchdowns",
            )
        ),
    )

    # Passing TDs are intentionally excluded.
    projected_scoring_tds = (
        projected_rushing_tds
        + projected_receiving_tds
    )

    projected_scoring_tds = clamp(
        projected_scoring_tds,
        0.0,
        MAX_GAME_TD_PROJECTION,
    )

    rates = scoring_rates(metrics)

    player_usage_factor = usage_factor(
        metrics
    )

    historical_rush_lambda = (
        rates["rushing_td_rate"]
        * player_usage_factor
    )

    historical_rec_lambda = (
        rates["receiving_td_rate"]
        * player_usage_factor
    )

    historical_lambda = (
        historical_rush_lambda
        + historical_rec_lambda
    )

    # If the single-game projection is zero, historical scoring
    # ability still provides a legitimate baseline.
    #
    # If the game projection is non-zero, blend both signals.
    if projected_scoring_tds > 0:
        touchdown_lambda = (
            historical_lambda
            * HISTORICAL_RATE_WEIGHT
            + projected_scoring_tds
            * GAME_PROJECTION_WEIGHT
        )
    else:
        touchdown_lambda = historical_lambda

    availability_factor, injury_status = (
        player_availability(player)
    )

    touchdown_lambda *= availability_factor

    touchdown_lambda = clamp(
        touchdown_lambda,
        0.0,
        MAX_TOUCHDOWN_LAMBDA,
    )

    if touchdown_lambda < MIN_MEANINGFUL_LAMBDA:
        touchdown_lambda = 0.0

    probability = poisson_at_least_one(
        touchdown_lambda
    )

    # Split the final lambda between rushing and receiving based
    # on the blended component shares.
    rush_signal = (
        historical_rush_lambda
        * HISTORICAL_RATE_WEIGHT
        + min(
            projected_rushing_tds,
            MAX_GAME_TD_PROJECTION,
        )
        * GAME_PROJECTION_WEIGHT
    )

    rec_signal = (
        historical_rec_lambda
        * HISTORICAL_RATE_WEIGHT
        + min(
            projected_receiving_tds,
            MAX_GAME_TD_PROJECTION,
        )
        * GAME_PROJECTION_WEIGHT
    )

    signal_total = rush_signal + rec_signal

    if signal_total > 0:
        rushing_lambda = (
            touchdown_lambda
            * rush_signal
            / signal_total
        )

        receiving_lambda = (
            touchdown_lambda
            * rec_signal
            / signal_total
        )

    else:
        rushing_lambda = 0.0
        receiving_lambda = 0.0

    rushing_probability = poisson_at_least_one(
        rushing_lambda
    )

    receiving_probability = poisson_at_least_one(
        receiving_lambda
    )

    environment = player.get(
        "environment",
        {},
    )

    matchup = player.get(
        "matchup",
        {},
    )

    return {
        "player_id": clean_text(
            player.get("player_id")
        ),
        "player": clean_text(
            player.get("player")
        ),
        "team": clean_text(
            player.get("team")
        ).upper(),
        "opponent": clean_text(
            player.get("opponent")
        ).upper(),
        "position": position,
        "game_id": clean_text(
            player.get("game_id")
        ),

        "touchdown_probability": round(
            probability * 100.0,
            1,
        ),

        "touchdown_lambda": round(
            touchdown_lambda,
            4,
        ),

        "scoring": {
            "rushing_td_probability": round(
                rushing_probability * 100.0,
                1,
            ),
            "receiving_td_probability": round(
                receiving_probability * 100.0,
                1,
            ),
            "rushing_lambda": round(
                rushing_lambda,
                4,
            ),
            "receiving_lambda": round(
                receiving_lambda,
                4,
            ),
        },

        "inputs": {
            "current_games": int(
                rates["games"]
            ),

            "current_rushing_td_rate": round(
                rates[
                    "current_rushing_td_rate"
                ],
                3,
            ),

            "current_receiving_td_rate": round(
                rates[
                    "current_receiving_td_rate"
                ],
                3,
            ),

            "career_rushing_td_rate": round(
                rates[
                    "career_rushing_td_rate"
                ],
                3,
            ),

            "career_receiving_td_rate": round(
                rates[
                    "career_receiving_td_rate"
                ],
                3,
            ),

            "regressed_rushing_td_rate": round(
                rates["rushing_td_rate"],
                3,
            ),

            "regressed_receiving_td_rate": round(
                rates["receiving_td_rate"],
                3,
            ),

            "usage_factor": round(
                player_usage_factor,
                3,
            ),

            "projected_rushing_tds": round(
                projected_rushing_tds,
                3,
            ),

            "projected_receiving_tds": round(
                projected_receiving_tds,
                3,
            ),

            "availability_factor": round(
                availability_factor,
                3,
            ),

            "injury_status": injury_status,
        },

        "environment": {
            "projected_team_points": round(
                f(
                    environment.get(
                        "projected_team_points"
                    )
                ),
                1,
            ),

            "scoring_factor": round(
                f(
                    environment.get(
                        "scoring_factor"
                    ),
                    1.0,
                ),
                3,
            ),
        },

        "matchup": {
            "overall_factor": round(
                f(
                    matchup.get(
                        "overall_factor"
                    ),
                    1.0,
                ),
                3,
            ),

            "passing_factor": round(
                f(
                    matchup.get(
                        "passing_factor"
                    ),
                    1.0,
                ),
                3,
            ),

            "rushing_factor": round(
                f(
                    matchup.get(
                        "rushing_factor"
                    ),
                    1.0,
                ),
                3,
            ),
        },

        "model": {
            "method": "blended_poisson",
            "passing_touchdowns_count": False,
        },
    }


def build_touchdown_payload(
    source_file: Path,
    metrics_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    payload = load_json(
        source_file,
        default={},
    )

    players = extract_players(payload)

    output_players = []

    missing_metrics = 0

    for player in players:
        player_id = clean_text(
            player.get("player_id")
        )

        metrics = metrics_lookup.get(
            player_id,
            {},
        )

        if not metrics:
            missing_metrics += 1

        result = (
            build_player_touchdown_projection(
                player,
                metrics,
            )
        )

        if result is not None:
            output_players.append(result)

    output_players.sort(
        key=lambda row: (
            clean_text(row.get("game_id")),
            clean_text(row.get("team")),
            clean_text(row.get("position")),
            -f(
                row.get(
                    "touchdown_probability"
                )
            ),
            clean_text(row.get("player")),
        )
    )

    counts = {
        "total": len(output_players),
        "QB": 0,
        "RB": 0,
        "WR": 0,
        "TE": 0,
    }

    for player in output_players:
        position = player.get("position")

        if position in counts:
            counts[position] += 1

    return {
        "players": output_players,

        "counts": counts,

        "diagnostics": {
            "missing_player_metrics": (
                missing_metrics
            ),
        },

        "model": {
            "name": (
                "Alpha Wagerz NFL "
                "Touchdown Probability Model"
            ),
            "version": "2.0",
            "sportsbook_independent": True,
            "probability_method": (
                "1 - exp(-lambda)"
            ),
            "passing_touchdowns_count": False,
            "current_rate_stabilization_games": (
                CURRENT_RATE_STABILIZATION_GAMES
            ),
            "historical_rate_weight": (
                HISTORICAL_RATE_WEIGHT
            ),
            "game_projection_weight": (
                GAME_PROJECTION_WEIGHT
            ),
        },
    }


def write_payload(
    payload: dict[str, Any],
    output_file: Path,
    web_output_file: Path,
) -> None:
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


def build_touchdown_projections() -> None:
    print(
        "🏈 Building NFL touchdown probabilities...",
        flush=True,
    )

    metrics_payload = load_json(
        PLAYER_METRICS_FILE,
        default={},
    )

    metrics_lookup = build_metrics_lookup(
        metrics_payload
    )

    if PLAYER_PROJECTIONS_FILE.exists():
        current = build_touchdown_payload(
            PLAYER_PROJECTIONS_FILE,
            metrics_lookup,
        )

        write_payload(
            current,
            OUTPUT_FILE,
            WEB_OUTPUT_FILE,
        )

        print(
            "   Current slate: "
            f"{current['counts']['total']} players",
            flush=True,
        )

    if NEXT_PLAYER_PROJECTIONS_FILE.exists():
        next_payload = build_touchdown_payload(
            NEXT_PLAYER_PROJECTIONS_FILE,
            metrics_lookup,
        )

        write_payload(
            next_payload,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
        )

        print(
            "   Next slate: "
            f"{next_payload['counts']['total']} players",
            flush=True,
        )

    print(
        "✅ NFL touchdown probabilities complete.",
        flush=True,
    )


if __name__ == "__main__":
    build_touchdown_projections()
