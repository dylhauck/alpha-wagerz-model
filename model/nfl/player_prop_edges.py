from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


MODEL_ROOT = Path(__file__).resolve().parents[2]

NFL_DIR = MODEL_ROOT / "data" / "processed" / "nfl"
WEB_NFL_DIR = MODEL_ROOT.parent / "alpha-wagerz-web" / "public" / "data" / "nfl"

PLAYER_PROJECTIONS_FILE = NFL_DIR / "player_projections.json"
PLAYER_PROPS_FILE = NFL_DIR / "player_props.json"

NEXT_PLAYER_PROJECTIONS_FILE = NFL_DIR / "next" / "player_projections.json"
NEXT_PLAYER_PROPS_FILE = NFL_DIR / "next" / "player_props.json"

OUTPUT_FILE = NFL_DIR / "player_prop_edges.json"
NEXT_OUTPUT_FILE = NFL_DIR / "next" / "player_prop_edges.json"

WEB_OUTPUT_FILE = WEB_NFL_DIR / "player_prop_edges.json"
NEXT_WEB_OUTPUT_FILE = WEB_NFL_DIR / "next" / "player_prop_edges.json"


MIN_EDGES = {
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


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_name(value: Any) -> str:
    return " ".join(clean_text(value).lower().split())


def number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def get_projection_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if isinstance(payload, dict):
        for key in ("players", "projections", "player_projections"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]

    return []


def get_prop_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("props", [])
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]

    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    return []


def find_numeric_recursive(
    value: Any,
    keys: set[str],
) -> float | None:
    if not isinstance(value, dict):
        return None

    for key, item in value.items():
        if key in keys:
            parsed = number(item)
            if parsed is not None:
                return parsed

    for item in value.values():
        if isinstance(item, dict):
            found = find_numeric_recursive(item, keys)
            if found is not None:
                return found

    return None


PROJECTION_KEYS = {
    "passing_yards": {
        "passing_yards",
        "pass_yards",
        "projected_passing_yards",
    },
    "passing_touchdowns": {
        "passing_touchdowns",
        "passing_tds",
        "pass_tds",
        "projected_passing_touchdowns",
    },
    "passing_attempts": {
        "passing_attempts",
        "pass_attempts",
    },
    "passing_completions": {
        "passing_completions",
        "completions",
    },
    "interceptions": {
        "interceptions",
        "passing_interceptions",
        "interceptions_thrown",
    },
    "rushing_yards": {
        "rushing_yards",
        "rush_yards",
        "projected_rushing_yards",
    },
    "rushing_attempts": {
        "rushing_attempts",
        "carries",
    },
    "receiving_yards": {
        "receiving_yards",
        "rec_yards",
        "projected_receiving_yards",
    },
    "receptions": {
        "receptions",
        "projected_receptions",
    },
    "receiving_targets": {
        "receiving_targets",
        "targets",
    },
    "longest_reception": {
        "longest_reception",
    },
    "longest_rush": {
        "longest_rush",
    },
}


def projected_stat(
    player: dict[str, Any],
    prop_type: str,
) -> float | None:
    keys = PROJECTION_KEYS.get(prop_type)
    if not keys:
        return None

    return find_numeric_recursive(player, keys)


def projection_lookup(
    payload: Any,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}

    for player in get_projection_rows(payload):
        player_id = clean_text(
            player.get("player_id")
            or player.get("gsis_id")
        )
        name = normalize_name(
            player.get("player_name")
            or player.get("name")
        )

        if player_id:
            by_id[player_id] = player
        if name:
            by_name[name] = player

    return by_id, by_name


def confidence_score(
    prop_type: str,
    absolute_edge: float,
) -> float:
    threshold = MIN_EDGES.get(prop_type, 1.0)

    strength = clamp(
        absolute_edge / max(threshold * 3.0, 0.01),
        0.0,
        1.0,
    )

    return round(
        45.0 + strength * 50.0,
        1,
    )


def confidence_label(score: float) -> str:
    if score >= 80:
        return "ELITE"
    if score >= 70:
        return "STRONG"
    if score >= 60:
        return "GOOD"
    if score >= 50:
        return "LEAN"
    return "PASS"


def build_edge_file(
    projection_file: Path,
    prop_file: Path,
    output_file: Path,
    web_output_file: Path,
) -> dict[str, Any]:
    projection_payload = load_json(
        projection_file,
        default={},
    )
    prop_payload = load_json(
        prop_file,
        default={},
    )

    by_id, by_name = projection_lookup(
        projection_payload
    )

    results: list[dict[str, Any]] = []
    missing_players = 0
    unsupported_props = 0

    for prop in get_prop_rows(prop_payload):
        prop_type = clean_text(prop.get("prop_type"))

        # Anytime TD needs a probability model rather than simply comparing
        # a numeric stat projection to a line, so it is intentionally left
        # for the dedicated TD-probability model.
        if prop_type == "anytime_touchdown":
            unsupported_props += 1
            continue

        if prop_type not in PROJECTION_KEYS:
            unsupported_props += 1
            continue

        player_id = clean_text(prop.get("player_id"))
        player_name = normalize_name(prop.get("player_name"))

        player = None
        if player_id:
            player = by_id.get(player_id)
        if player is None and player_name:
            player = by_name.get(player_name)

        if player is None:
            missing_players += 1
            continue

        projection = projected_stat(
            player,
            prop_type,
        )
        line = number(prop.get("line"))

        if projection is None or line is None:
            unsupported_props += 1
            continue

        raw_edge = projection - line
        absolute_edge = abs(raw_edge)

        minimum = MIN_EDGES.get(prop_type, 1.0)

        if absolute_edge < minimum:
            continue

        side = "OVER" if raw_edge > 0 else "UNDER"
        confidence = confidence_score(
            prop_type,
            absolute_edge,
        )

        results.append(
            {
                "game_id": prop.get("game_id"),
                "away_team": prop.get("away_team"),
                "home_team": prop.get("home_team"),

                "player_id": (
                    prop.get("player_id")
                    or player.get("player_id")
                    or player.get("gsis_id")
                ),
                "player_name": prop.get("player_name"),
                "team": prop.get("team") or player.get("team"),
                "position": prop.get("position") or player.get("position"),

                "prop_type": prop_type,
                "sportsbook": prop.get("sportsbook"),

                "market_line": round(line, 2),
                "model_projection": round(projection, 2),

                "selection": f"{side} {line:g}",
                "edge": round(absolute_edge, 2),
                "signed_edge": round(raw_edge, 2),

                "over_odds": prop.get("over_odds"),
                "under_odds": prop.get("under_odds"),

                "confidence_score": confidence,
                "confidence_label": confidence_label(confidence),
            }
        )

    results.sort(
        key=lambda x: (
            x.get("confidence_score", 0),
            x.get("edge", 0),
        ),
        reverse=True,
    )

    payload = {
        "ranked_props": results,
        "counts": {
            "edges": len(results),
            "missing_players": missing_players,
            "unsupported_or_missing_projection": unsupported_props,
        },
        "model": {
            "name": "Alpha Wagerz NFL Player Prop Edge Engine",
            "version": "1.0",
            "sportsbook_lines_used_only_for_edge": True,
            "projection_models_remain_independent": True,
        },
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    web_output_file.parent.mkdir(parents=True, exist_ok=True)

    save_json(payload, output_file)
    save_json(payload, web_output_file)

    print(f"   ✅ {len(results)} player prop edges")
    if missing_players:
        print(f"   ⚠️ Missing projected players: {missing_players}")
    if unsupported_props:
        print(
            "   ⚠️ Unsupported props / missing model projection: "
            f"{unsupported_props}"
        )
    print(f"      {output_file}")
    print(f"      {web_output_file}")

    return payload


def build_nfl_player_prop_edges():
    print("\n🎯 BUILDING NFL PLAYER PROP EDGES\n")

    if not PLAYER_PROJECTIONS_FILE.exists():
        raise RuntimeError(
            "NFL player projections not found. "
            "Run model.nfl.player_projections first."
        )

    if not PLAYER_PROPS_FILE.exists():
        raise RuntimeError(
            "NFL player props not found. "
            "Run providers.nfl_player_props first."
        )

    print("   Current slate")
    build_edge_file(
        PLAYER_PROJECTIONS_FILE,
        PLAYER_PROPS_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
    )

    if (
        NEXT_PLAYER_PROJECTIONS_FILE.exists()
        and NEXT_PLAYER_PROPS_FILE.exists()
    ):
        print("\n   Next slate")
        build_edge_file(
            NEXT_PLAYER_PROJECTIONS_FILE,
            NEXT_PLAYER_PROPS_FILE,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
        )

    print("\n✅ NFL PLAYER PROP EDGES COMPLETE\n")
    return True


if __name__ == "__main__":
    build_nfl_player_prop_edges()
