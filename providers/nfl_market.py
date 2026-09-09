from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


MODEL_ROOT = Path(__file__).resolve().parents[1]

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

SLATE_FILE = (
    NFL_DIR
    / "slate.json"
)

NEXT_SLATE_FILE = (
    NFL_DIR
    / "next"
    / "slate.json"
)

ODDS_FILE = (
    NFL_DIR
    / "odds.json"
)

NEXT_ODDS_FILE = (
    NFL_DIR
    / "next"
    / "odds.json"
)

OUTPUT_FILE = (
    NFL_DIR
    / "market.json"
)

NEXT_OUTPUT_FILE = (
    NFL_DIR
    / "next"
    / "market.json"
)

WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "market.json"
)

NEXT_WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "next"
    / "market.json"
)


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


def american_to_implied_probability(
    odds: float | None,
) -> float | None:
    if odds is None:
        return None

    if odds == 0:
        return None

    if odds > 0:
        return 100.0 / (
            odds + 100.0
        )

    return (
        abs(odds)
        / (
            abs(odds)
            + 100.0
        )
    )


def remove_moneyline_vig(
    away_odds: float | None,
    home_odds: float | None,
) -> tuple[
    float | None,
    float | None,
]:
    away_raw = (
        american_to_implied_probability(
            away_odds
        )
    )

    home_raw = (
        american_to_implied_probability(
            home_odds
        )
    )

    if (
        away_raw is None
        or home_raw is None
    ):
        return (
            away_raw,
            home_raw,
        )

    total = (
        away_raw
        + home_raw
    )

    if total <= 0:
        return (
            away_raw,
            home_raw,
        )

    return (
        away_raw / total,
        home_raw / total,
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


def infer_spreads(
    raw_spread: float | None,
    away_moneyline: float | None,
    home_moneyline: float | None,
) -> tuple[
    float | None,
    float | None,
]:
    if raw_spread is None:
        return (
            None,
            None,
        )

    spread = abs(
        raw_spread
    )

    if (
        away_moneyline is not None
        and home_moneyline is not None
    ):
        if (
            home_moneyline
            < away_moneyline
        ):
            return (
                spread,
                -spread,
            )

        if (
            away_moneyline
            < home_moneyline
        ):
            return (
                -spread,
                spread,
            )

    # nflverse schedules commonly expose the closing spread
    # as the home-team perspective. Preserve that convention
    # when moneylines are unavailable.
    home_spread = (
        raw_spread
    )

    return (
        -home_spread,
        home_spread,
    )


def implied_team_totals(
    game_total: float | None,
    away_spread: float | None,
    home_spread: float | None,
) -> tuple[
    float | None,
    float | None,
]:
    if (
        game_total is None
        or away_spread is None
        or home_spread is None
    ):
        return (
            None,
            None,
        )

    # Spread is expressed from each team's perspective:
    # favorite negative, underdog positive.
    away_total = (
        game_total
        - away_spread
    ) / 2.0

    home_total = (
        game_total
        - home_spread
    ) / 2.0

    return (
        round(
            away_total,
            2,
        ),
        round(
            home_total,
            2,
        ),
    )


def normalize_game_market(
    game: dict[str, Any],
) -> dict[str, Any]:
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

    spread_line = f(
        game.get(
            "spread_line"
        )
    )

    total_line = f(
        game.get(
            "total_line"
        )
    )

    away_moneyline = f(
        game.get(
            "away_moneyline"
        )
    )

    home_moneyline = f(
        game.get(
            "home_moneyline"
        )
    )

    away_spread, home_spread = (
        infer_spreads(
            spread_line,
            away_moneyline,
            home_moneyline,
        )
    )

    (
        away_no_vig_probability,
        home_no_vig_probability,
    ) = remove_moneyline_vig(
        away_moneyline,
        home_moneyline,
    )

    (
        away_team_total,
        home_team_total,
    ) = implied_team_totals(
        total_line,
        away_spread,
        home_spread,
    )

    available_markets = []

    if (
        away_moneyline is not None
        and home_moneyline is not None
    ):
        available_markets.append(
            "moneyline"
        )

    if (
        away_spread is not None
        and home_spread is not None
    ):
        available_markets.append(
            "spread"
        )

    if total_line is not None:
        available_markets.append(
            "game_total"
        )

    if (
        away_team_total is not None
        and home_team_total is not None
    ):
        available_markets.append(
            "implied_team_total"
        )

    return {
        "game_id": (
            game.get(
                "game_id"
            )
        ),

        "season": (
            game.get(
                "season"
            )
        ),

        "week": (
            game.get(
                "week"
            )
        ),

        "game_type": (
            game.get(
                "game_type"
            )
        ),

        "game_date": (
            game.get(
                "game_date"
            )
        ),

        "game_time": (
            game.get(
                "game_time"
            )
        ),

        "away_team": (
            away_team
        ),

        "home_team": (
            home_team
        ),

        "moneyline": {
            "away": (
                away_moneyline
            ),

            "home": (
                home_moneyline
            ),

            "away_implied_probability": (
                round(
                    american_to_implied_probability(
                        away_moneyline
                    )
                    or 0.0,
                    4,
                )
                if away_moneyline
                is not None
                else None
            ),

            "home_implied_probability": (
                round(
                    american_to_implied_probability(
                        home_moneyline
                    )
                    or 0.0,
                    4,
                )
                if home_moneyline
                is not None
                else None
            ),

            "away_no_vig_probability": (
                round(
                    away_no_vig_probability,
                    4,
                )
                if away_no_vig_probability
                is not None
                else None
            ),

            "home_no_vig_probability": (
                round(
                    home_no_vig_probability,
                    4,
                )
                if home_no_vig_probability
                is not None
                else None
            ),
        },

        "spread": {
            "away": (
                round(
                    away_spread,
                    2,
                )
                if away_spread
                is not None
                else None
            ),

            "home": (
                round(
                    home_spread,
                    2,
                )
                if home_spread
                is not None
                else None
            ),

            "raw_spread_line": (
                spread_line
            ),
        },

        "game_total": (
            total_line
        ),

        "team_totals": {
            "away": (
                away_team_total
            ),

            "home": (
                home_team_total
            ),

            "source": (
                "derived_from_spread_and_total"
            ),
        },

        "implied_team_totals": {
            "away": away_team_total,
            "home": home_team_total,
            "source": (
                "derived_from_live_spread_and_total"
                if (
                    away_team_total is not None
                    and home_team_total is not None
                )
                else None
            ),
        },

        "posted_team_totals": {
            "away": {
                "line": None,
                "over_price": None,
                "under_price": None,
            },
            "home": {
                "line": None,
                "over_price": None,
                "under_price": None,
            },
            "source": None,
        },

        "available_markets": (
            available_markets
        ),

        "source": {
            "provider": (
                "nflverse_slate"
            ),

            "sportsbook": (
                game.get(
                    "bookmaker"
                )
                or game.get(
                    "sportsbook"
                )
                or "consensus/closing"
            ),

            "note": (
                "Normalized from the sportsbook "
                "fields already present in the "
                "NFL slate. Projection models do "
                "not consume this file."
            ),
        },
    }


# =========================================================
# BUILD
# =========================================================

def build_live_market(
    live_game: dict[str, Any],
    slate_game: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slate_game = slate_game or {}

    away_team = normalize_team(
        live_game.get("away_team")
        or slate_game.get("away_team")
    )
    home_team = normalize_team(
        live_game.get("home_team")
        or slate_game.get("home_team")
    )

    bookmakers = live_game.get("bookmakers", [])
    if not isinstance(bookmakers, list):
        bookmakers = []

    selected = bookmakers[0] if bookmakers else {}
    markets = (
        selected.get("markets", {})
        if isinstance(selected, dict)
        else {}
    )

    moneyline = (
        markets.get("moneyline", {})
        if isinstance(markets, dict)
        else {}
    )
    spread = (
        markets.get("spread", {})
        if isinstance(markets, dict)
        else {}
    )
    total = (
        markets.get("game_total", {})
        if isinstance(markets, dict)
        else {}
    )
    team_total = (
        markets.get("team_total", {})
        if isinstance(markets, dict)
        else {}
    )

    away_team_total_market = (
        team_total.get("away", {})
        if isinstance(team_total, dict)
        else {}
    )
    home_team_total_market = (
        team_total.get("home", {})
        if isinstance(team_total, dict)
        else {}
    )

    away_moneyline = f(moneyline.get("away"))
    home_moneyline = f(moneyline.get("home"))
    away_spread = f(spread.get("away"))
    home_spread = f(spread.get("home"))
    total_line = f(total.get("line"))

    posted_away_team_total = f(
        away_team_total_market.get(
            "line"
        )
    )
    posted_home_team_total = f(
        home_team_total_market.get(
            "line"
        )
    )

    posted_away_over_price = f(
        away_team_total_market.get(
            "over_price"
        )
    )
    posted_away_under_price = f(
        away_team_total_market.get(
            "under_price"
        )
    )
    posted_home_over_price = f(
        home_team_total_market.get(
            "over_price"
        )
    )
    posted_home_under_price = f(
        home_team_total_market.get(
            "under_price"
        )
    )

    (
        away_no_vig_probability,
        home_no_vig_probability,
    ) = remove_moneyline_vig(
        away_moneyline,
        home_moneyline,
    )

    (
        away_team_total,
        home_team_total,
    ) = implied_team_totals(
        total_line,
        away_spread,
        home_spread,
    )

    available_markets = []

    if away_moneyline is not None and home_moneyline is not None:
        available_markets.append("moneyline")

    if away_spread is not None and home_spread is not None:
        available_markets.append("spread")

    if total_line is not None:
        available_markets.append("game_total")

    if (
        posted_away_team_total is not None
        or posted_home_team_total is not None
    ):
        available_markets.append(
            "team_total"
        )

    if (
        away_team_total is not None
        and home_team_total is not None
    ):
        available_markets.append(
            "implied_team_total"
        )

    return {
        "game_id": slate_game.get("game_id") or live_game.get("event_id"),
        "event_id": live_game.get("event_id"),
        "season": slate_game.get("season"),
        "week": slate_game.get("week"),
        "game_type": slate_game.get("game_type"),
        "game_date": slate_game.get("game_date"),
        "game_time": slate_game.get("game_time"),
        "commence_time": live_game.get("commence_time"),
        "away_team": away_team,
        "home_team": home_team,

        "moneyline": {
            "away": away_moneyline,
            "home": home_moneyline,
            "away_implied_probability": (
                round(
                    american_to_implied_probability(away_moneyline) or 0.0,
                    4,
                )
                if away_moneyline is not None
                else None
            ),
            "home_implied_probability": (
                round(
                    american_to_implied_probability(home_moneyline) or 0.0,
                    4,
                )
                if home_moneyline is not None
                else None
            ),
            "away_no_vig_probability": (
                round(away_no_vig_probability, 4)
                if away_no_vig_probability is not None
                else None
            ),
            "home_no_vig_probability": (
                round(home_no_vig_probability, 4)
                if home_no_vig_probability is not None
                else None
            ),
        },

        "spread": {
            "away": away_spread,
            "home": home_spread,
            "away_price": f(spread.get("away_price")),
            "home_price": f(spread.get("home_price")),
        },

        "game_total": total_line,

        "game_total_prices": {
            "over": f(total.get("over_price")),
            "under": f(total.get("under_price")),
        },

        "team_totals": {
            "away": posted_away_team_total,
            "home": posted_home_team_total,
            "source": (
                "sportsbook"
                if (
                    posted_away_team_total is not None
                    or posted_home_team_total is not None
                )
                else None
            ),
        },

        "posted_team_totals": {
            "away": {
                "line": (
                    posted_away_team_total
                ),
                "over_price": (
                    posted_away_over_price
                ),
                "under_price": (
                    posted_away_under_price
                ),
            },
            "home": {
                "line": (
                    posted_home_team_total
                ),
                "over_price": (
                    posted_home_over_price
                ),
                "under_price": (
                    posted_home_under_price
                ),
            },
            "source": (
                "sportsbook"
                if (
                    posted_away_team_total
                    is not None
                    or posted_home_team_total
                    is not None
                )
                else None
            ),
        },

        "available_markets": available_markets,

        "source": {
            "provider": "the_odds_api",
            "sportsbook": (
                selected.get("title")
                or selected.get("key")
                or None
            ),
            "sportsbook_key": selected.get("key"),
            "last_update": selected.get("last_update"),
            "note": (
                "Live sportsbook market selected from the configured "
                "bookmaker preference. Projection models do not consume "
                "this file."
            ),
        },

        "bookmakers": bookmakers,
    }


def build_market_file(
    slate_file: Path,
    odds_file: Path,
    output_file: Path,
    web_output_file: Path,
) -> dict[str, Any]:
    slate_payload = load_json(
        slate_file,
        default={},
    )

    slate_games = get_games(
        slate_payload
    )

    slate_lookup = {
        (
            normalize_team(
                game.get("away_team")
                or game.get("away")
            ),
            normalize_team(
                game.get("home_team")
                or game.get("home")
            ),
        ): game
        for game in slate_games
    }

    live_payload = (
        load_json(
            odds_file,
            default={},
        )
        if odds_file.exists()
        else {}
    )

    live_games = get_games(
        live_payload
    )

    live_lookup = {
        (
            normalize_team(game.get("away_team")),
            normalize_team(game.get("home_team")),
        ): game
        for game in live_games
    }

    markets = []

    for key, slate_game in slate_lookup.items():
        live_game = live_lookup.get(key)

        if live_game:
            markets.append(
                build_live_market(
                    live_game,
                    slate_game,
                )
            )
        else:
            # Safe fallback preserves the working nflverse slate market
            # behavior when live odds are unavailable for a game.
            markets.append(
                normalize_game_market(
                    slate_game
                )
            )

    output = {
        "games": markets,

        "counts": {
            "games": len(markets),
            "live_games": sum(
                1
                for game in markets
                if game.get("source", {}).get("provider")
                == "the_odds_api"
            ),
            "fallback_games": sum(
                1
                for game in markets
                if game.get("source", {}).get("provider")
                != "the_odds_api"
            ),
            "moneyline": sum(
                1
                for game in markets
                if "moneyline"
                in game.get("available_markets", [])
            ),
            "spread": sum(
                1
                for game in markets
                if "spread"
                in game.get("available_markets", [])
            ),
            "game_total": sum(
                1
                for game in markets
                if "game_total"
                in game.get("available_markets", [])
            ),
            "team_total": sum(
                1
                for game in markets
                if "team_total"
                in game.get("available_markets", [])
            ),
        },

        "model": {
            "name": "Alpha Wagerz NFL Market Normalizer",
            "version": "2.0",
            "projection_independent": True,
            "live_odds_preferred": True,
            "slate_fallback_enabled": True,
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
        output,
        output_file,
    )

    save_json(
        output,
        web_output_file,
    )

    print(
        f"   ✅ {len(markets)} NFL market games"
    )
    print(
        f"      Live: {output['counts']['live_games']} | "
        f"Fallback: {output['counts']['fallback_games']}"
    )
    print(
        f"      {output_file}"
    )
    print(
        f"      {web_output_file}"
    )

    return output

def build_nfl_market():
    print(
        "\n💰 BUILDING NFL "
        "MARKET DATA\n"
    )

    if not SLATE_FILE.exists():
        raise RuntimeError(
            f"NFL slate not found: "
            f"{SLATE_FILE}"
        )

    print(
        "   Current slate"
    )

    build_market_file(
        SLATE_FILE,
        ODDS_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
    )

    if NEXT_SLATE_FILE.exists():
        print(
            "\n   Next slate"
        )

        build_market_file(
            NEXT_SLATE_FILE,
            NEXT_ODDS_FILE,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
        )

    print(
        "\n✅ NFL MARKET DATA COMPLETE\n"
    )

    return True


if __name__ == "__main__":
    build_nfl_market()
