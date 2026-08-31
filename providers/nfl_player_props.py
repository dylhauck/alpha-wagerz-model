from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


MODEL_ROOT = Path(__file__).resolve().parents[1]

NFL_DIR = MODEL_ROOT / "data" / "processed" / "nfl"
WEB_NFL_DIR = MODEL_ROOT.parent / "alpha-wagerz-web" / "public" / "data" / "nfl"

SLATE_FILE = NFL_DIR / "slate.json"
NEXT_SLATE_FILE = NFL_DIR / "next" / "slate.json"

ODDS_FILE = NFL_DIR / "odds.json"
NEXT_ODDS_FILE = NFL_DIR / "next" / "odds.json"

OUTPUT_FILE = NFL_DIR / "player_props.json"
NEXT_OUTPUT_FILE = NFL_DIR / "next" / "player_props.json"

WEB_OUTPUT_FILE = WEB_NFL_DIR / "player_props.json"
NEXT_WEB_OUTPUT_FILE = WEB_NFL_DIR / "next" / "player_props.json"


# Canonical prop names used everywhere downstream.
PROP_ALIASES = {
    "passing_yards": "passing_yards",
    "pass_yards": "passing_yards",
    "player_pass_yards": "passing_yards",

    "passing_touchdowns": "passing_touchdowns",
    "passing_tds": "passing_touchdowns",
    "pass_tds": "passing_touchdowns",
    "player_pass_tds": "passing_touchdowns",

    "passing_attempts": "passing_attempts",
    "pass_attempts": "passing_attempts",

    "passing_completions": "passing_completions",
    "completions": "passing_completions",

    "interceptions": "interceptions",
    "passing_interceptions": "interceptions",
    "interceptions_thrown": "interceptions",

    "rushing_yards": "rushing_yards",
    "rush_yards": "rushing_yards",
    "player_rush_yards": "rushing_yards",

    "rushing_attempts": "rushing_attempts",
    "carries": "rushing_attempts",

    "receiving_yards": "receiving_yards",
    "rec_yards": "receiving_yards",
    "player_reception_yards": "receiving_yards",

    "receptions": "receptions",
    "player_receptions": "receptions",

    "receiving_targets": "receiving_targets",
    "targets": "receiving_targets",

    "anytime_touchdown": "anytime_touchdown",
    "anytime_td": "anytime_touchdown",
    "player_anytime_td": "anytime_touchdown",

    "longest_reception": "longest_reception",
    "longest_rush": "longest_rush",
}


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_team(value: Any) -> str:
    team = clean_text(value).upper()
    aliases = {
        "LA": "LAR",
        "JAC": "JAX",
        "WSH": "WAS",
        "OAK": "LV",
        "SD": "LAC",
        "STL": "LAR",
    }
    return aliases.get(team, team)


def normalize_prop_type(value: Any) -> str:
    key = (
        clean_text(value)
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
    )
    return PROP_ALIASES.get(key, key)


def number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def get_games(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    if isinstance(payload, dict):
        games = payload.get("games", [])
        if isinstance(games, list):
            return [x for x in games if isinstance(x, dict)]

    return []


def extract_raw_props(game: dict[str, Any]) -> list[dict[str, Any]]:
    """
    This normalizer deliberately does not scrape or invent sportsbook props.

    It accepts player-prop rows already attached by a provider under one of
    these common game keys. When a live sportsbook/API provider is added,
    that provider can populate the same structure without changing the
    downstream edge engine.
    """
    for key in (
        "player_props",
        "props",
        "player_markets",
        "prop_markets",
    ):
        rows = game.get(key)
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]

    return []


def normalize_prop(
    raw: dict[str, Any],
    game: dict[str, Any],
) -> dict[str, Any] | None:
    player_name = clean_text(
        raw.get("player_name")
        or raw.get("player")
        or raw.get("name")
    )

    if not player_name:
        return None

    prop_type = normalize_prop_type(
        raw.get("prop_type")
        or raw.get("market")
        or raw.get("stat")
        or raw.get("key")
    )

    if not prop_type:
        return None

    line = number(
        raw.get("line")
        if raw.get("line") is not None
        else raw.get("point")
    )

    # Anytime TD can exist without a numeric line.
    if line is None and prop_type != "anytime_touchdown":
        return None

    over_odds = number(
        raw.get("over_odds")
        or raw.get("over_price")
    )

    under_odds = number(
        raw.get("under_odds")
        or raw.get("under_price")
    )

    yes_odds = number(
        raw.get("yes_odds")
        or raw.get("price")
        or raw.get("odds")
    )

    return {
        "game_id": game.get("game_id"),
        "season": game.get("season"),
        "week": game.get("week"),
        "game_date": game.get("game_date"),
        "game_time": game.get("game_time"),
        "away_team": normalize_team(game.get("away_team") or game.get("away")),
        "home_team": normalize_team(game.get("home_team") or game.get("home")),

        "player_id": raw.get("player_id"),
        "player_name": player_name,
        "team": normalize_team(raw.get("team")),
        "position": clean_text(raw.get("position")).upper(),

        "prop_type": prop_type,
        "line": line,

        "over_odds": over_odds,
        "under_odds": under_odds,
        "yes_odds": yes_odds,

        "sportsbook": (
            raw.get("sportsbook")
            or raw.get("bookmaker")
            or raw.get("book")
        ),

        "source": raw.get("source") or "slate_player_props",
    }


def get_live_games(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        games = payload.get("games", [])
        if isinstance(games, list):
            return [x for x in games if isinstance(x, dict)]
    return []


def build_prop_file(
    slate_file: Path,
    odds_file: Path,
    output_file: Path,
    web_output_file: Path,
) -> dict[str, Any]:
    slate = load_json(slate_file, default={})
    games = get_games(slate)

    slate_lookup = {
        (
            normalize_team(game.get("away_team") or game.get("away")),
            normalize_team(game.get("home_team") or game.get("home")),
        ): game
        for game in games
    }

    live_payload = (
        load_json(odds_file, default={})
        if odds_file.exists()
        else {}
    )

    rows: list[dict[str, Any]] = []

    for live_game in get_live_games(live_payload):
        key = (
            normalize_team(live_game.get("away_team")),
            normalize_team(live_game.get("home_team")),
        )

        slate_game = slate_lookup.get(key, {})

        game_context = {
            **slate_game,
            "game_id": (
                slate_game.get("game_id")
                or live_game.get("event_id")
            ),
            "away_team": key[0],
            "home_team": key[1],
        }

        for raw in live_game.get("player_props", []):
            if not isinstance(raw, dict):
                continue

            normalized = normalize_prop(
                raw,
                game_context,
            )

            if normalized:
                normalized["event_id"] = live_game.get("event_id")
                normalized["source"] = (
                    raw.get("source")
                    or "the_odds_api"
                )
                rows.append(normalized)

    # Preserve backward compatibility if no live prop feed exists yet.
    if not rows:
        for game in games:
            for raw in extract_raw_props(game):
                normalized = normalize_prop(raw, game)
                if normalized:
                    rows.append(normalized)

    rows.sort(
        key=lambda x: (
            x.get("game_date") or "",
            x.get("game_time") or "",
            x.get("player_name") or "",
            x.get("prop_type") or "",
            x.get("sportsbook") or "",
        )
    )

    payload = {
        "props": rows,
        "counts": {
            "games": len(games),
            "props": len(rows),
            "live_props": sum(
                1
                for row in rows
                if row.get("source") == "the_odds_api"
            ),
        },
        "model": {
            "name": "Alpha Wagerz NFL Player Prop Normalizer",
            "version": "2.0",
            "projection_independent": True,
            "live_odds_preferred": True,
            "note": (
                "Consumes normalized live sportsbook player props from "
                "odds.json. It never manufactures sportsbook lines."
            ),
        },
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    web_output_file.parent.mkdir(parents=True, exist_ok=True)

    save_json(payload, output_file)
    save_json(payload, web_output_file)

    print(f"   ✅ {len(rows)} NFL player prop lines")
    print(
        f"      Live: {payload['counts']['live_props']}"
    )

    if not rows:
        print(
            "   ⚠️ No live player-prop rows are currently available."
        )

    print(f"      {output_file}")
    print(f"      {web_output_file}")

    return payload

def build_nfl_player_props():
    print("\n🏷️ BUILDING NFL PLAYER PROP MARKET\n")

    if not SLATE_FILE.exists():
        raise RuntimeError(f"NFL slate not found: {SLATE_FILE}")

    print("   Current slate")
    build_prop_file(
        SLATE_FILE,
        ODDS_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
    )

    if NEXT_SLATE_FILE.exists():
        print("\n   Next slate")
        build_prop_file(
            NEXT_SLATE_FILE,
            NEXT_ODDS_FILE,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
        )

    print("\n✅ NFL PLAYER PROP MARKET COMPLETE\n")
    return True


if __name__ == "__main__":
    build_nfl_player_props()
