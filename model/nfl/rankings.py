from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


MODEL_ROOT = Path(__file__).resolve().parents[2]

NFL_DIR = MODEL_ROOT / "data" / "processed" / "nfl"
WEB_NFL_DIR = MODEL_ROOT.parent / "alpha-wagerz-web" / "public" / "data" / "nfl"

EDGES_FILE = NFL_DIR / "edges.json"
PLAYER_PROP_EDGES_FILE = NFL_DIR / "player_prop_edges.json"
OUTPUT_FILE = NFL_DIR / "rankings.json"
WEB_OUTPUT_FILE = WEB_NFL_DIR / "rankings.json"

NEXT_EDGES_FILE = NFL_DIR / "next" / "edges.json"
NEXT_PLAYER_PROP_EDGES_FILE = NFL_DIR / "next" / "player_prop_edges.json"
NEXT_OUTPUT_FILE = NFL_DIR / "next" / "rankings.json"
NEXT_WEB_OUTPUT_FILE = WEB_NFL_DIR / "next" / "rankings.json"


# =========================================================
# RANKING RULES
# =========================================================
#
# This layer does NOT create new bets.
# It only ranks recommendations already produced by:
#
#   model/nfl/edge_engine.py
#   model/nfl/player_prop_edges.py
#
# Sportsbook data never enters the independent projection
# process here.
#
# No quota is enforced for Best Bets / Strong Plays / Leans.
# If nothing qualifies, the section is allowed to be empty.
# =========================================================

BEST_BET_MIN_CONFIDENCE = 80.0
STRONG_PLAY_MIN_CONFIDENCE = 70.0
LEAN_MIN_CONFIDENCE = 50.0

# A recommendation must already have a qualifying model edge.
# These values are used only as a secondary quality check when
# a normalized edge-strength value can be derived.
BEST_BET_MIN_EDGE_STRENGTH = 1.25
STRONG_PLAY_MIN_EDGE_STRENGTH = 1.00
LEAN_MIN_EDGE_STRENGTH = 0.50

GAME_EDGE_THRESHOLDS = {
    "moneyline": 0.025,
    "spread": 1.0,
    "game_total": 1.5,
    "team_total": 1.25,
}

PROP_EDGE_THRESHOLDS = {
    "passing_yards": 12.0,
    "passing_touchdowns": 0.30,
    "passing_attempts": 2.5,
    "passing_completions": 2.0,
    "interceptions": 0.25,
    "rushing_yards": 7.0,
    "rushing_attempts": 2.0,
    "receiving_yards": 7.0,
    "receptions": 0.75,
    "receiving_targets": 1.25,
    "longest_reception": 4.0,
    "longest_rush": 4.0,
}


# =========================================================
# HELPERS
# =========================================================

def f(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_key(value: Any) -> str:
    return (
        clean_text(value)
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
        .replace("/", "_")
    )


def first_value(
    row: dict[str, Any],
    *keys: str,
) -> Any:
    for key in keys:
        if key in row and row.get(key) is not None:
            return row.get(key)
    return None


def first_float(
    row: dict[str, Any],
    *keys: str,
    default: float = 0.0,
) -> float:
    return f(
        first_value(row, *keys),
        default,
    )


def extract_list(
    payload: Any,
    *keys: str,
) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [
            row
            for row in payload
            if isinstance(row, dict)
        ]

    if not isinstance(payload, dict):
        return []

    for key in keys:
        rows = payload.get(key)

        if isinstance(rows, list):
            return [
                row
                for row in rows
                if isinstance(row, dict)
            ]

    return []


def confidence_value(
    row: dict[str, Any],
) -> float:
    raw = first_value(
        row,
        "confidence",
        "confidence_score",
        "score",
    )

    if isinstance(raw, dict):
        raw = first_value(
            raw,
            "score",
            "value",
            "confidence",
        )

    value = f(raw, 0.0)

    # Accept 0-1 confidence if an upstream file ever uses it.
    if 0.0 < value <= 1.0:
        value *= 100.0

    return max(
        0.0,
        min(
            100.0,
            value,
        ),
    )


def existing_label(
    row: dict[str, Any],
) -> str:
    return clean_text(
        first_value(
            row,
            "confidence_label",
            "label",
            "rating",
            "tier",
        )
    ).upper()


def game_market_type(
    row: dict[str, Any],
) -> str:
    raw = normalize_key(
        first_value(
            row,
            "market_type",
            "market",
            "bet_type",
            "type",
        )
    )

    aliases = {
        "ml": "moneyline",
        "money_line": "moneyline",
        "moneyline": "moneyline",
        "spread": "spread",
        "point_spread": "spread",
        "game_total": "game_total",
        "total": "game_total",
        "totals": "game_total",
        "over_under": "game_total",
        "team_total": "team_total",
        "team_totals": "team_total",
    }

    return aliases.get(
        raw,
        raw,
    )


def prop_type(
    row: dict[str, Any],
) -> str:
    raw = normalize_key(
        first_value(
            row,
            "prop_type",
            "market_type",
            "market",
            "stat",
            "stat_key",
        )
    )

    aliases = {
        "pass_yards": "passing_yards",
        "passing_yds": "passing_yards",
        "pass_yds": "passing_yards",
        "pass_touchdowns": "passing_touchdowns",
        "passing_tds": "passing_touchdowns",
        "pass_tds": "passing_touchdowns",
        "pass_attempts": "passing_attempts",
        "pass_completions": "passing_completions",
        "completions": "passing_completions",
        "passing_interceptions": "interceptions",
        "interceptions_thrown": "interceptions",
        "rush_yards": "rushing_yards",
        "rushing_yds": "rushing_yards",
        "rush_attempts": "rushing_attempts",
        "carries": "rushing_attempts",
        "reception_yards": "receiving_yards",
        "receiving_yds": "receiving_yards",
        "targets": "receiving_targets",
        "reception_longest": "longest_reception",
        "rush_longest": "longest_rush",
    }

    return aliases.get(
        raw,
        raw,
    )


def absolute_edge(
    row: dict[str, Any],
) -> float:
    return abs(
        first_float(
            row,
            "edge",
            "edge_absolute",
            "absolute_edge",
            "raw_edge",
            "edge_value",
            default=0.0,
        )
    )


def game_edge_strength(
    row: dict[str, Any],
) -> float:
    market = game_market_type(row)
    edge = absolute_edge(row)

    threshold = GAME_EDGE_THRESHOLDS.get(
        market
    )

    if not threshold:
        return 0.0

    return edge / threshold


def prop_edge_strength(
    row: dict[str, Any],
) -> float:
    market = prop_type(row)
    edge = absolute_edge(row)

    threshold = PROP_EDGE_THRESHOLDS.get(
        market
    )

    if not threshold:
        return 0.0

    return edge / threshold


def is_pass(
    row: dict[str, Any],
) -> bool:
    label = existing_label(row)

    if label == "PASS":
        return True

    recommendation = clean_text(
        first_value(
            row,
            "recommendation",
            "pick",
            "side",
        )
    ).upper()

    return recommendation == "PASS"


def ranking_tier(
    confidence: float,
    edge_strength: float,
    upstream_label: str,
    pass_row: bool,
) -> str:
    if pass_row:
        return "PASS"

    # Preserve a stricter upstream PASS if present.
    if upstream_label == "PASS":
        return "PASS"

    if (
        confidence >= BEST_BET_MIN_CONFIDENCE
        and edge_strength >= BEST_BET_MIN_EDGE_STRENGTH
    ):
        return "BEST BET"

    if (
        confidence >= STRONG_PLAY_MIN_CONFIDENCE
        and edge_strength >= STRONG_PLAY_MIN_EDGE_STRENGTH
    ):
        return "STRONG PLAY"

    if (
        confidence >= LEAN_MIN_CONFIDENCE
        and edge_strength >= LEAN_MIN_EDGE_STRENGTH
    ):
        return "LEAN"

    return "PASS"


def ranking_score(
    confidence: float,
    edge_strength: float,
) -> float:
    # Confidence is the dominant signal. Edge strength is capped
    # so one unusually large raw edge cannot overwhelm reliability.
    normalized_edge = min(
        max(edge_strength, 0.0),
        3.0,
    ) / 3.0 * 100.0

    score = (
        confidence * 0.70
        + normalized_edge * 0.30
    )

    return round(
        max(
            0.0,
            min(
                100.0,
                score,
            ),
        ),
        2,
    )


def matchup_text(
    row: dict[str, Any],
) -> str:
    matchup = clean_text(
        first_value(
            row,
            "matchup",
            "game",
        )
    )

    if matchup:
        return matchup

    away = clean_text(
        first_value(
            row,
            "away_team",
            "away",
        )
    )

    home = clean_text(
        first_value(
            row,
            "home_team",
            "home",
        )
    )

    if away and home:
        return f"{away} @ {home}"

    return ""


def pick_text(
    row: dict[str, Any],
) -> str:
    return clean_text(
        first_value(
            row,
            "recommendation",
            "pick",
            "selection",
            "side",
        )
    )


def line_value(
    row: dict[str, Any],
) -> Any:
    return first_value(
        row,
        "line",
        "market_line",
        "sportsbook_line",
        "book_line",
    )


def odds_value(
    row: dict[str, Any],
) -> Any:
    return first_value(
        row,
        "odds",
        "price",
        "sportsbook_odds",
        "american_odds",
    )


def projection_value(
    row: dict[str, Any],
) -> Any:
    return first_value(
        row,
        "projection",
        "projected_value",
        "model_projection",
        "projected_line",
        "model_value",
    )


# =========================================================
# NORMALIZATION
# =========================================================

def normalize_game_bet(
    row: dict[str, Any],
) -> dict[str, Any]:
    confidence = confidence_value(row)
    strength = game_edge_strength(row)
    upstream = existing_label(row)

    tier = ranking_tier(
        confidence,
        strength,
        upstream,
        is_pass(row),
    )

    return {
        "ranking_type": "game_bet",
        "tier": tier,
        "ranking_score": ranking_score(
            confidence,
            strength,
        ),
        "confidence": round(
            confidence,
            2,
        ),
        "upstream_label": upstream,
        "edge_strength": round(
            strength,
            4,
        ),
        "edge": first_value(
            row,
            "edge",
            "edge_absolute",
            "absolute_edge",
            "raw_edge",
            "edge_value",
        ),
        "market_type": game_market_type(
            row
        ),
        "game_id": first_value(
            row,
            "game_id",
            "event_id",
        ),
        "matchup": matchup_text(row),
        "away_team": first_value(
            row,
            "away_team",
            "away",
        ),
        "home_team": first_value(
            row,
            "home_team",
            "home",
        ),
        "team": first_value(
            row,
            "team",
            "team_abbr",
        ),
        "pick": pick_text(row),
        "line": line_value(row),
        "odds": odds_value(row),
        "sportsbook": first_value(
            row,
            "sportsbook",
            "bookmaker",
            "book",
        ),
        "projection": projection_value(
            row
        ),
        "projection_confidence": first_value(
            row,
            "projection_confidence",
            "model_confidence",
        ),
        "source": "nfl_game_edges",
        "raw": row,
    }


def normalize_player_prop(
    row: dict[str, Any],
) -> dict[str, Any]:
    confidence = confidence_value(row)
    strength = prop_edge_strength(row)
    upstream = existing_label(row)

    tier = ranking_tier(
        confidence,
        strength,
        upstream,
        is_pass(row),
    )

    return {
        "ranking_type": "player_prop",
        "tier": tier,
        "ranking_score": ranking_score(
            confidence,
            strength,
        ),
        "confidence": round(
            confidence,
            2,
        ),
        "upstream_label": upstream,
        "edge_strength": round(
            strength,
            4,
        ),
        "edge": first_value(
            row,
            "edge",
            "edge_absolute",
            "absolute_edge",
            "raw_edge",
            "edge_value",
        ),
        "prop_type": prop_type(row),
        "game_id": first_value(
            row,
            "game_id",
            "event_id",
        ),
        "matchup": matchup_text(row),
        "away_team": first_value(
            row,
            "away_team",
            "away",
        ),
        "home_team": first_value(
            row,
            "home_team",
            "home",
        ),
        "player_id": first_value(
            row,
            "player_id",
            "gsis_id",
        ),
        "player_name": first_value(
            row,
            "player_name",
            "name",
            "player",
        ),
        "team": first_value(
            row,
            "team",
            "team_abbr",
        ),
        "position": first_value(
            row,
            "position",
            "pos",
        ),
        "pick": pick_text(row),
        "line": line_value(row),
        "odds": odds_value(row),
        "sportsbook": first_value(
            row,
            "sportsbook",
            "bookmaker",
            "book",
        ),
        "projection": projection_value(
            row
        ),
        "source": "nfl_player_prop_edges",
        "raw": row,
    }


# =========================================================
# SORTING / SECTIONS
# =========================================================

TIER_ORDER = {
    "BEST BET": 0,
    "STRONG PLAY": 1,
    "LEAN": 2,
    "PASS": 3,
}


def sort_key(
    row: dict[str, Any],
) -> tuple[Any, ...]:
    return (
        TIER_ORDER.get(
            clean_text(
                row.get("tier")
            ).upper(),
            99,
        ),
        -f(
            row.get(
                "ranking_score"
            ),
            0.0,
        ),
        -f(
            row.get(
                "confidence"
            ),
            0.0,
        ),
        -f(
            row.get(
                "edge_strength"
            ),
            0.0,
        ),
        clean_text(
            row.get(
                "matchup"
            )
        ),
        clean_text(
            row.get(
                "player_name"
            )
        ),
    )


def section(
    rows: list[dict[str, Any]],
    tier: str,
) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if row.get("tier") == tier
        ],
        key=sort_key,
    )


def ranked_non_pass(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if row.get("tier") != "PASS"
        ],
        key=sort_key,
    )


# =========================================================
# BUILD
# =========================================================

def build_rankings_payload(
    game_edges_payload: Any,
    prop_edges_payload: Any,
) -> dict[str, Any]:
    game_rows = extract_list(
        game_edges_payload,
        "ranked_bets",
        "bets",
        "edges",
        "recommendations",
    )

    prop_rows = extract_list(
        prop_edges_payload,
        "ranked_props",
        "props",
        "edges",
        "recommendations",
    )

    game_bets = [
        normalize_game_bet(row)
        for row in game_rows
    ]

    player_props = [
        normalize_player_prop(row)
        for row in prop_rows
    ]

    all_rows = (
        game_bets
        + player_props
    )

    all_rows.sort(
        key=sort_key
    )

    best_bets = section(
        all_rows,
        "BEST BET",
    )

    strong_plays = section(
        all_rows,
        "STRONG PLAY",
    )

    leans = section(
        all_rows,
        "LEAN",
    )

    passes = section(
        all_rows,
        "PASS",
    )

    return {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "model": "nfl_rankings",
        "model_version": "1.0",
        "philosophy": {
            "independent_projection": True,
            "sportsbook_used_for_projection": False,
            "forced_picks": False,
            "ranking_score_weights": {
                "confidence": 0.70,
                "edge_strength": 0.30,
            },
        },
        "thresholds": {
            "best_bet": {
                "minimum_confidence": (
                    BEST_BET_MIN_CONFIDENCE
                ),
                "minimum_edge_strength": (
                    BEST_BET_MIN_EDGE_STRENGTH
                ),
            },
            "strong_play": {
                "minimum_confidence": (
                    STRONG_PLAY_MIN_CONFIDENCE
                ),
                "minimum_edge_strength": (
                    STRONG_PLAY_MIN_EDGE_STRENGTH
                ),
            },
            "lean": {
                "minimum_confidence": (
                    LEAN_MIN_CONFIDENCE
                ),
                "minimum_edge_strength": (
                    LEAN_MIN_EDGE_STRENGTH
                ),
            },
        },
        "counts": {
            "game_bets": len(
                game_bets
            ),
            "player_props": len(
                player_props
            ),
            "all_candidates": len(
                all_rows
            ),
            "best_bets": len(
                best_bets
            ),
            "strong_plays": len(
                strong_plays
            ),
            "leans": len(
                leans
            ),
            "passes": len(
                passes
            ),
        },
        "best_bets": best_bets,
        "strong_plays": strong_plays,
        "leans": leans,
        "passes": passes,
        "ranked_recommendations": (
            ranked_non_pass(
                all_rows
            )
        ),
        "game_bets": sorted(
            game_bets,
            key=sort_key,
        ),
        "player_props": sorted(
            player_props,
            key=sort_key,
        ),
    }


def build_rankings_file(
    edges_file: Path,
    prop_edges_file: Path,
    output_file: Path,
    web_output_file: Path,
    label: str,
) -> bool:
    if not edges_file.exists():
        print(
            f"   ⚠️ {label}: missing "
            f"{edges_file}"
        )
        return False

    if not prop_edges_file.exists():
        print(
            f"   ⚠️ {label}: missing "
            f"{prop_edges_file}"
        )
        return False

    game_edges_payload = load_json(
        edges_file,
        default={},
    )

    prop_edges_payload = load_json(
        prop_edges_file,
        default={},
    )

    payload = build_rankings_payload(
        game_edges_payload,
        prop_edges_payload,
    )

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

    counts = payload["counts"]

    print(
        f"\n   {label}"
    )
    print(
        f"   ✅ Best Bets: "
        f"{counts['best_bets']}"
    )
    print(
        f"   ✅ Strong Plays: "
        f"{counts['strong_plays']}"
    )
    print(
        f"   ✅ Leans: "
        f"{counts['leans']}"
    )
    print(
        f"   ⏭️ Passes: "
        f"{counts['passes']}"
    )
    print(
        f"      {output_file}"
    )
    print(
        f"      {web_output_file}"
    )

    return True


def build_nfl_rankings():
    print(
        "\n🏆 BUILDING NFL "
        "RANKINGS / BEST BETS\n"
    )

    current_ok = build_rankings_file(
        EDGES_FILE,
        PLAYER_PROP_EDGES_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
        "Current slate",
    )

    next_ok = False

    if (
        NEXT_EDGES_FILE.exists()
        and NEXT_PLAYER_PROP_EDGES_FILE.exists()
    ):
        next_ok = build_rankings_file(
            NEXT_EDGES_FILE,
            NEXT_PLAYER_PROP_EDGES_FILE,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
            "Next slate",
        )
    else:
        print(
            "\n   Next slate"
        )
        print(
            "   ⚠️ Next-slate edge files "
            "not both available; skipped."
        )

    print(
        "\n✅ NFL RANKINGS / "
        "BEST BETS COMPLETE\n"
    )

    return (
        current_ok
        or next_ok
    )


if __name__ == "__main__":
    build_nfl_rankings()

