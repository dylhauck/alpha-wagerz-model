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

GAME_PROJECTIONS_FILE = (
    NFL_DIR
    / "game_projections.json"
)

MARKET_FILE = (
    NFL_DIR
    / "market.json"
)

NEXT_GAME_PROJECTIONS_FILE = (
    NFL_DIR
    / "next"
    / "game_projections.json"
)

NEXT_MARKET_FILE = (
    NFL_DIR
    / "next"
    / "market.json"
)

OUTPUT_FILE = (
    NFL_DIR
    / "edges.json"
)

NEXT_OUTPUT_FILE = (
    NFL_DIR
    / "next"
    / "edges.json"
)

WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "edges.json"
)

NEXT_WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "next"
    / "edges.json"
)


# =========================================================
# SETTINGS
# =========================================================

MIN_MONEYLINE_EDGE = 0.025
MIN_SPREAD_EDGE = 1.0
MIN_TOTAL_EDGE = 1.5
MIN_TEAM_TOTAL_EDGE = 1.25


# =========================================================
# HELPERS
# =========================================================

def f(
    value: Any,
    default: float | None = None,
) -> float | None:
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


def get_games(
    payload: Any,
) -> list[dict[str, Any]]:
    if isinstance(
        payload,
        list,
    ):
        return [
            row
            for row in payload
            if isinstance(
                row,
                dict,
            )
        ]

    if isinstance(
        payload,
        dict,
    ):
        games = payload.get(
            "games",
            [],
        )

        if isinstance(
            games,
            list,
        ):
            return [
                row
                for row in games
                if isinstance(
                    row,
                    dict,
                )
            ]

    return []


def game_key(
    game: dict[str, Any],
) -> tuple[str, str]:
    return (
        normalize_team(
            game.get(
                "away_team"
            )
            or game.get(
                "away"
            )
        ),
        normalize_team(
            game.get(
                "home_team"
            )
            or game.get(
                "home"
            )
        ),
    )


def get_projected_points(
    projection: dict[str, Any],
    side: str,
) -> float | None:
    candidates = [
        projection.get(
            f"{side}_projected_points"
        ),
        (
            projection.get(
                side,
                {}
            ).get(
                "projected_points"
            )
            if isinstance(
                projection.get(
                    side
                ),
                dict,
            )
            else None
        ),
        (
            projection.get(
                "projection",
                {}
            ).get(
                side
            )
            if isinstance(
                projection.get(
                    "projection"
                ),
                dict,
            )
            else None
        ),
    ]

    for candidate in candidates:
        value = f(
            candidate
        )

        if value is not None:
            return value

    return None


def get_projected_total(
    projection: dict[str, Any],
    away_points: float | None,
    home_points: float | None,
) -> float | None:
    candidates = [
        projection.get(
            "projected_total"
        ),
        projection.get(
            "game_total"
        ),
        (
            projection.get(
                "projection",
                {}
            ).get(
                "total"
            )
            if isinstance(
                projection.get(
                    "projection"
                ),
                dict,
            )
            else None
        ),
    ]

    for candidate in candidates:
        value = f(
            candidate
        )

        if value is not None:
            return value

    if (
        away_points is not None
        and home_points is not None
    ):
        return (
            away_points
            + home_points
        )

    return None


def get_win_probability(
    projection: dict[str, Any],
    side: str,
) -> float | None:
    win_probability = (
        projection.get(
            "win_probability",
            {}
        )
    )

    if not isinstance(
        win_probability,
        dict,
    ):
        return None

    value = f(
        win_probability.get(
            side
        )
    )

    if value is None:
        return None

    if value > 1.0:
        value = (
            value / 100.0
        )

    return clamp(
        value,
        0.0,
        1.0,
    )


def confidence_score(
    edge_strength: float,
    projection_confidence: float | None,
) -> float:
    base = clamp(
        edge_strength,
        0.0,
        1.0,
    )

    if projection_confidence is None:
        projection_factor = 0.50

    else:
        projection_factor = (
            projection_confidence
        )

        if projection_factor > 1.0:
            projection_factor = (
                projection_factor
                / 100.0
            )

        projection_factor = clamp(
            projection_factor,
            0.0,
            1.0,
        )

    score = (
        base * 0.65
        + projection_factor * 0.35
    )

    return round(
        clamp(
            score * 100.0,
            0.0,
            100.0,
        ),
        1,
    )


def confidence_label(
    score: float,
) -> str:
    if score >= 80:
        return "ELITE"

    if score >= 70:
        return "STRONG"

    if score >= 60:
        return "GOOD"

    if score >= 50:
        return "LEAN"

    return "PASS"


def recommendation(
    market_type: str,
    selection: str,
    edge: float,
    confidence: float,
) -> dict[str, Any]:
    return {
        "market": (
            market_type
        ),

        "selection": (
            selection
        ),

        "edge": round(
            edge,
            3,
        ),

        "confidence_score": (
            confidence
        ),

        "confidence_label": (
            confidence_label(
                confidence
            )
        ),
    }


# =========================================================
# GAME EDGE
# =========================================================

def build_game_edge(
    projection: dict[str, Any],
    market: dict[str, Any],
) -> dict[str, Any]:
    away_team = normalize_team(
        market.get(
            "away_team"
        )
    )

    home_team = normalize_team(
        market.get(
            "home_team"
        )
    )

    away_points = (
        get_projected_points(
            projection,
            "away",
        )
    )

    home_points = (
        get_projected_points(
            projection,
            "home",
        )
    )

    projected_total = (
        get_projected_total(
            projection,
            away_points,
            home_points,
        )
    )

    projected_margin = None

    if (
        home_points is not None
        and away_points is not None
    ):
        projected_margin = (
            home_points
            - away_points
        )

    projection_confidence = f(
        projection.get(
            "projection_confidence"
        )
    )

    recommendations = []

    # -------------------------
    # MONEYLINE
    # -------------------------

    moneyline = market.get(
        "moneyline",
        {},
    )

    if isinstance(
        moneyline,
        dict,
    ):
        away_model_probability = (
            get_win_probability(
                projection,
                "away",
            )
        )

        home_model_probability = (
            get_win_probability(
                projection,
                "home",
            )
        )

        away_market_probability = f(
            moneyline.get(
                "away_no_vig_probability"
            )
        )

        home_market_probability = f(
            moneyline.get(
                "home_no_vig_probability"
            )
        )

        if (
            away_model_probability
            is not None
            and away_market_probability
            is not None
        ):
            away_ml_edge = (
                away_model_probability
                - away_market_probability
            )

            if (
                away_ml_edge
                >= MIN_MONEYLINE_EDGE
            ):
                strength = clamp(
                    away_ml_edge
                    / 0.12,
                    0.0,
                    1.0,
                )

                recommendations.append(
                    recommendation(
                        "moneyline",
                        away_team,
                        away_ml_edge,
                        confidence_score(
                            strength,
                            projection_confidence,
                        ),
                    )
                )

        if (
            home_model_probability
            is not None
            and home_market_probability
            is not None
        ):
            home_ml_edge = (
                home_model_probability
                - home_market_probability
            )

            if (
                home_ml_edge
                >= MIN_MONEYLINE_EDGE
            ):
                strength = clamp(
                    home_ml_edge
                    / 0.12,
                    0.0,
                    1.0,
                )

                recommendations.append(
                    recommendation(
                        "moneyline",
                        home_team,
                        home_ml_edge,
                        confidence_score(
                            strength,
                            projection_confidence,
                        ),
                    )
                )

    # -------------------------
    # SPREAD
    # -------------------------

    spread = market.get(
        "spread",
        {},
    )

    if (
        isinstance(
            spread,
            dict,
        )
        and projected_margin
        is not None
    ):
        home_spread = f(
            spread.get(
                "home"
            )
        )

        away_spread = f(
            spread.get(
                "away"
            )
        )

        if home_spread is not None:
            home_cover_margin = (
                projected_margin
                + home_spread
            )

            if (
                home_cover_margin
                >= MIN_SPREAD_EDGE
            ):
                strength = clamp(
                    home_cover_margin
                    / 7.0,
                    0.0,
                    1.0,
                )

                recommendations.append(
                    recommendation(
                        "spread",
                        (
                            f"{home_team} "
                            f"{home_spread:+g}"
                        ),
                        home_cover_margin,
                        confidence_score(
                            strength,
                            projection_confidence,
                        ),
                    )
                )

        if away_spread is not None:
            away_cover_margin = (
                -projected_margin
                + away_spread
            )

            if (
                away_cover_margin
                >= MIN_SPREAD_EDGE
            ):
                strength = clamp(
                    away_cover_margin
                    / 7.0,
                    0.0,
                    1.0,
                )

                recommendations.append(
                    recommendation(
                        "spread",
                        (
                            f"{away_team} "
                            f"{away_spread:+g}"
                        ),
                        away_cover_margin,
                        confidence_score(
                            strength,
                            projection_confidence,
                        ),
                    )
                )

    # -------------------------
    # GAME TOTAL
    # -------------------------

    market_total = f(
        market.get(
            "game_total"
        )
    )

    if (
        projected_total is not None
        and market_total is not None
    ):
        total_edge = (
            projected_total
            - market_total
        )

        if (
            abs(
                total_edge
            )
            >= MIN_TOTAL_EDGE
        ):
            selection = (
                f"OVER {market_total:g}"
                if total_edge > 0
                else f"UNDER {market_total:g}"
            )

            strength = clamp(
                abs(
                    total_edge
                )
                / 8.0,
                0.0,
                1.0,
            )

            recommendations.append(
                recommendation(
                    "game_total",
                    selection,
                    abs(
                        total_edge
                    ),
                    confidence_score(
                        strength,
                        projection_confidence,
                    ),
                )
            )

    # -------------------------
    # TEAM TOTALS
    # -------------------------

    team_totals = market.get(
        "team_totals",
        {},
    )

    if isinstance(
        team_totals,
        dict,
    ):
        away_market_total = f(
            team_totals.get(
                "away"
            )
        )

        home_market_total = f(
            team_totals.get(
                "home"
            )
        )

        if (
            away_points is not None
            and away_market_total
            is not None
        ):
            edge = (
                away_points
                - away_market_total
            )

            if (
                abs(
                    edge
                )
                >= MIN_TEAM_TOTAL_EDGE
            ):
                selection = (
                    f"{away_team} OVER "
                    f"{away_market_total:g}"
                    if edge > 0
                    else
                    f"{away_team} UNDER "
                    f"{away_market_total:g}"
                )

                strength = clamp(
                    abs(
                        edge
                    )
                    / 5.0,
                    0.0,
                    1.0,
                )

                recommendations.append(
                    recommendation(
                        "team_total",
                        selection,
                        abs(
                            edge
                        ),
                        confidence_score(
                            strength,
                            projection_confidence,
                        ),
                    )
                )

        if (
            home_points is not None
            and home_market_total
            is not None
        ):
            edge = (
                home_points
                - home_market_total
            )

            if (
                abs(
                    edge
                )
                >= MIN_TEAM_TOTAL_EDGE
            ):
                selection = (
                    f"{home_team} OVER "
                    f"{home_market_total:g}"
                    if edge > 0
                    else
                    f"{home_team} UNDER "
                    f"{home_market_total:g}"
                )

                strength = clamp(
                    abs(
                        edge
                    )
                    / 5.0,
                    0.0,
                    1.0,
                )

                recommendations.append(
                    recommendation(
                        "team_total",
                        selection,
                        abs(
                            edge
                        ),
                        confidence_score(
                            strength,
                            projection_confidence,
                        ),
                    )
                )

    recommendations.sort(
        key=lambda row: (
            row.get(
                "confidence_score",
                0.0,
            ),
            row.get(
                "edge",
                0.0,
            ),
        ),
        reverse=True,
    )

    return {
        "game_id": (
            market.get(
                "game_id"
            )
            or projection.get(
                "game_id"
            )
        ),

        "away_team": (
            away_team
        ),

        "home_team": (
            home_team
        ),

        "model_projection": {
            "away_points": (
                round(
                    away_points,
                    2,
                )
                if away_points
                is not None
                else None
            ),

            "home_points": (
                round(
                    home_points,
                    2,
                )
                if home_points
                is not None
                else None
            ),

            "total": (
                round(
                    projected_total,
                    2,
                )
                if projected_total
                is not None
                else None
            ),

            "home_margin": (
                round(
                    projected_margin,
                    2,
                )
                if projected_margin
                is not None
                else None
            ),

            "away_win_probability": (
                get_win_probability(
                    projection,
                    "away",
                )
            ),

            "home_win_probability": (
                get_win_probability(
                    projection,
                    "home",
                )
            ),

            "projection_confidence": (
                projection_confidence
            ),
        },

        "market": (
            market
        ),

        "recommendations": (
            recommendations
        ),

        "best_bet": (
            recommendations[0]
            if recommendations
            else None
        ),
    }


# =========================================================
# BUILD
# =========================================================

def build_edge_file(
    projection_file: Path,
    market_file: Path,
    output_file: Path,
    web_output_file: Path,
) -> dict[str, Any]:
    projection_payload = load_json(
        projection_file,
        default={},
    )

    market_payload = load_json(
        market_file,
        default={},
    )

    projection_lookup = {
        game_key(
            game
        ): game
        for game in get_games(
            projection_payload
        )
        if all(
            game_key(
                game
            )
        )
    }

    edges = []
    missing_projection = 0

    for market in get_games(
        market_payload
    ):
        key = game_key(
            market
        )

        projection = (
            projection_lookup.get(
                key
            )
        )

        if not projection:
            missing_projection += 1
            continue

        edges.append(
            build_game_edge(
                projection,
                market,
            )
        )

    ranked_bets = []

    for game in edges:
        for bet in game.get(
            "recommendations",
            [],
        ):
            ranked_bets.append(
                {
                    "game_id": (
                        game.get(
                            "game_id"
                        )
                    ),

                    "away_team": (
                        game.get(
                            "away_team"
                        )
                    ),

                    "home_team": (
                        game.get(
                            "home_team"
                        )
                    ),

                    **bet,
                }
            )

    ranked_bets.sort(
        key=lambda row: (
            row.get(
                "confidence_score",
                0.0,
            ),
            row.get(
                "edge",
                0.0,
            ),
        ),
        reverse=True,
    )

    payload = {
        "games": (
            edges
        ),

        "ranked_bets": (
            ranked_bets
        ),

        "counts": {
            "games": len(
                edges
            ),

            "bets": len(
                ranked_bets
            ),

            "missing_projection": (
                missing_projection
            ),
        },

        "model": {
            "name": (
                "Alpha Wagerz NFL "
                "Edge & Confidence Engine"
            ),

            "version": (
                "1.0"
            ),

            "sportsbook_lines_used_only_for_edge": (
                True
            ),

            "projection_models_remain_independent": (
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
        f"   ✅ {len(edges)} "
        f"games evaluated"
    )

    print(
        f"   ✅ {len(ranked_bets)} "
        f"betting edges"
    )

    if missing_projection:
        print(
            f"   ⚠️ Missing game "
            f"projections: "
            f"{missing_projection}"
        )

    print(
        f"      {output_file}"
    )

    print(
        f"      {web_output_file}"
    )

    return payload


def build_nfl_edges():
    print(
        "\n📈 BUILDING NFL "
        "EDGES & CONFIDENCE\n"
    )

    if not GAME_PROJECTIONS_FILE.exists():
        raise RuntimeError(
            "NFL game projections not found. "
            "Run model.nfl.game_projections first."
        )

    if not MARKET_FILE.exists():
        raise RuntimeError(
            "NFL market data not found. "
            "Run providers.nfl_market first."
        )

    print(
        "   Current slate"
    )

    build_edge_file(
        GAME_PROJECTIONS_FILE,
        MARKET_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
    )

    if (
        NEXT_GAME_PROJECTIONS_FILE.exists()
        and
        NEXT_MARKET_FILE.exists()
    ):
        print(
            "\n   Next slate"
        )

        build_edge_file(
            NEXT_GAME_PROJECTIONS_FILE,
            NEXT_MARKET_FILE,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
        )

    print(
        "\n✅ NFL EDGES & "
        "CONFIDENCE COMPLETE\n"
    )

    return True


if __name__ == "__main__":
    build_nfl_edges()
