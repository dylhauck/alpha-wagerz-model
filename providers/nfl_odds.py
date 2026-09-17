from __future__ import annotations

import gzip
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from utils.json_utils import load_json, save_json


MODEL_ROOT = Path(__file__).resolve().parents[1]

NFL_DIR = MODEL_ROOT / "data" / "processed" / "nfl"
WEB_NFL_DIR = MODEL_ROOT.parent / "alpha-wagerz-web" / "public" / "data" / "nfl"

SLATE_FILE = NFL_DIR / "slate.json"
NEXT_SLATE_FILE = NFL_DIR / "next" / "slate.json"

OUTPUT_FILE = NFL_DIR / "odds.json"
NEXT_OUTPUT_FILE = NFL_DIR / "next" / "odds.json"

WEB_OUTPUT_FILE = WEB_NFL_DIR / "odds.json"
NEXT_WEB_OUTPUT_FILE = WEB_NFL_DIR / "next" / "odds.json"


# =========================================================
# ODDS-API.IO
# =========================================================

API_KEY = os.getenv("ODDS_API_IO_KEY")

BASE_URL = os.getenv(
    "ODDS_API_IO_BASE",
    "https://api.odds-api.io/v3",
).rstrip("/")

SPORT = os.getenv(
    "NFL_ODDS_API_IO_SPORT",
    "american-football",
)

LEAGUE = os.getenv(
    "NFL_ODDS_API_IO_LEAGUE",
    "usa-nfl",
)

BOOKMAKERS = [
    value.strip()
    for value in os.getenv(
        "NFL_ODDS_API_IO_BOOKMAKERS",
        "FanDuel,DraftKings",
    ).split(",")
    if value.strip()
]

BOOKMAKER_PRIORITY = {
    name.lower(): index
    for index, name in enumerate(BOOKMAKERS)
}


# =========================================================
# TEAM NORMALIZATION
# =========================================================

TEAM_ALIASES = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}

ABBREVIATION_ALIASES = {
    "LA": "LAR",
    "JAC": "JAX",
    "WSH": "WAS",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def number(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except Exception:
        return None


def normalize_team(value: Any) -> str:
    text = clean_text(value)

    if text in TEAM_ALIASES:
        return TEAM_ALIASES[text]

    upper = text.upper()

    return ABBREVIATION_ALIASES.get(
        upper,
        upper,
    )


def get_games(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [
            row
            for row in payload
            if isinstance(row, dict)
        ]

    if isinstance(payload, dict):
        games = payload.get("games", [])

        if isinstance(games, list):
            return [
                row
                for row in games
                if isinstance(row, dict)
            ]

    return []


def game_key(
    away: Any,
    home: Any,
) -> tuple[str, str]:
    return (
        normalize_team(away),
        normalize_team(home),
    )


def slate_lookup(
    payload: Any,
) -> dict[
    tuple[str, str],
    dict[str, Any],
]:
    return {
        game_key(
            game.get("away_team")
            or game.get("away"),
            game.get("home_team")
            or game.get("home"),
        ): game
        for game in get_games(payload)
    }


# =========================================================
# HTTP
# =========================================================

def api_get(
    endpoint: str,
    params: dict[str, Any],
) -> Any:
    query = urlencode(
        {
            key: value
            for key, value in params.items()
            if value not in (
                None,
                "",
            )
        }
    )

    url = (
        f"{BASE_URL}/{endpoint.lstrip('/')}"
        f"?{query}"
    )

    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Alpha-Wagerz/1.0",
        },
    )

    try:
        with urlopen(
            request,
            timeout=30,
        ) as response:
            raw = response.read()

            content_encoding = (
                response.headers.get(
                    "Content-Encoding",
                    "",
                ).lower()
            )

            # Odds-API.io may return a gzip-compressed
            # response. Detect it either from the HTTP
            # header or directly from the gzip magic bytes.
            if (
                "gzip" in content_encoding
                or raw[:2] == b"\x1f\x8b"
            ):
                raw = gzip.decompress(raw)

            return json.loads(
                raw.decode("utf-8")
            )

    except HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        raise RuntimeError(
            f"Odds-API.io returned HTTP "
            f"{exc.code}: {body[:500]}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            f"Unable to reach Odds-API.io: "
            f"{exc}"
        ) from exc


# =========================================================
# EVENTS
# =========================================================

def fetch_events() -> list[dict[str, Any]]:
    now = datetime.now(
        timezone.utc
    )

    params: dict[str, Any] = {
        "apiKey": API_KEY,
        "sport": SPORT,
        "status": "pending",
        "from": (
            now
            - timedelta(days=1)
        ).isoformat(),
        "to": (
            now
            + timedelta(days=21)
        ).isoformat(),
    }

    if LEAGUE:
        params["league"] = LEAGUE

    payload = api_get(
        "events",
        params,
    )

    if not isinstance(
        payload,
        list,
    ):
        raise RuntimeError(
            "Unexpected Odds-API.io events "
            "response."
        )

    return [
        event
        for event in payload
        if isinstance(
            event,
            dict,
        )
    ]


def match_events_to_slate(
    events: list[dict[str, Any]],
    slate_payload: Any,
) -> list[
    tuple[
        dict[str, Any],
        dict[str, Any],
    ]
]:
    slate = slate_lookup(
        slate_payload
    )

    matches = []

    for event in events:
        key = game_key(
            event.get("away"),
            event.get("home"),
        )

        game = slate.get(
            key
        )

        if game:
            matches.append(
                (
                    event,
                    game,
                )
            )

    return matches


# =========================================================
# ODDS PARSING
# =========================================================

def bookmaker_items(
    payload: dict[str, Any],
) -> list[
    tuple[
        str,
        list[dict[str, Any]],
    ]
]:
    raw = payload.get(
        "bookmakers",
        {},
    )

    if not isinstance(
        raw,
        dict,
    ):
        return []

    items = []

    for bookmaker, markets in raw.items():
        if not isinstance(
            markets,
            list,
        ):
            continue

        items.append(
            (
                clean_text(
                    bookmaker
                ),
                [
                    market
                    for market in markets
                    if isinstance(
                        market,
                        dict,
                    )
                ],
            )
        )

    items.sort(
        key=lambda item: (
            BOOKMAKER_PRIORITY.get(
                item[0].lower(),
                999,
            ),
            item[0].lower(),
        )
    )

    return items


def market_name(
    market: dict[str, Any],
) -> str:
    return clean_text(
        market.get("name")
        or market.get("market")
        or market.get("type")
    )


def market_key(
    market: dict[str, Any],
) -> str:
    return (
        market_name(
            market
        )
        .lower()
        .replace("-", " ")
        .replace("_", " ")
    )


def odds_rows(
    market: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = market.get(
        "odds",
        [],
    )

    if not isinstance(
        rows,
        list,
    ):
        return []

    return [
        row
        for row in rows
        if isinstance(
            row,
            dict,
        )
    ]


def first_number(
    row: dict[str, Any],
    *keys: str,
) -> float | None:
    for key in keys:
        value = number(
            row.get(key)
        )

        if value is not None:
            return value

    return None


def decimal_to_american(
    decimal_odds: float | None,
) -> float | None:
    if decimal_odds is None or decimal_odds <= 1.0:
        return None

    if decimal_odds >= 2.0:
        american = (
            (decimal_odds - 1.0)
            * 100.0
        )
    else:
        american = (
            -100.0
            / (decimal_odds - 1.0)
        )

    return float(round(american))


def balanced_two_way_row(
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Odds-API.io can return alternate lines inside one Totals/Team Total
    market. The primary line is the row whose two-way prices are closest
    to balanced after converting decimal prices to implied probabilities.
    """
    candidates = []

    for index, row in enumerate(rows):
        line = first_number(
            row,
            "hdp",
            "line",
            "point",
        )
        over = first_number(
            row,
            "over",
            "overOdds",
            "over_odds",
        )
        under = first_number(
            row,
            "under",
            "underOdds",
            "under_odds",
        )

        if (
            line is None
            or over is None
            or under is None
            or over <= 1.0
            or under <= 1.0
        ):
            continue

        over_probability = 1.0 / over
        under_probability = 1.0 / under

        balance = abs(
            over_probability
            - under_probability
        )

        # Secondary tie-breaker favors normal two-way pricing near even
        # money rather than extreme alternate lines.
        distance_from_even = (
            abs(over - 2.0)
            + abs(under - 2.0)
        )

        candidates.append(
            (
                balance,
                distance_from_even,
                index,
                row,
            )
        )

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    return candidates[0][3]


def normalize_featured_markets(
    bookmaker: str,
    markets: list[dict[str, Any]],
    away_name: str,
    home_name: str,
) -> dict[str, Any]:
    output: dict[str, Any] = {}

    for market in markets:
        key = market_key(
            market
        )

        rows = odds_rows(
            market
        )

        if not rows:
            continue

        # -------------------------
        # MONEYLINE
        # -------------------------

        if key in {
            "ml",
            "moneyline",
            "money line",
            "match winner",
        }:
            away_price = None
            home_price = None

            # Odds-API.io NFL response:
            # {"home": "1.556", "away": "2.520"}
            for row in rows:
                direct_away = first_number(
                    row,
                    "away",
                )
                direct_home = first_number(
                    row,
                    "home",
                )

                if (
                    direct_away is not None
                    or direct_home is not None
                ):
                    away_price = decimal_to_american(
                        direct_away
                    )
                    home_price = decimal_to_american(
                        direct_home
                    )
                    break

                label = clean_text(
                    row.get("label")
                    or row.get("name")
                )

                row_price = first_number(
                    row,
                    "odds",
                    "price",
                    "value",
                )

                if (
                    normalize_team(label)
                    == normalize_team(away_name)
                    or label.lower()
                    in {"away", "2"}
                ):
                    away_price = decimal_to_american(
                        row_price
                    )

                elif (
                    normalize_team(label)
                    == normalize_team(home_name)
                    or label.lower()
                    in {"home", "1"}
                ):
                    home_price = decimal_to_american(
                        row_price
                    )

            if (
                away_price is not None
                and home_price is not None
            ):
                output["moneyline"] = {
                    "away": away_price,
                    "home": home_price,
                }

        # -------------------------
        # SPREAD
        # -------------------------

        elif key in {
            "spread",
            "handicap",
        }:
            away_line = None
            home_line = None
            away_price = None
            home_price = None

            # Odds-API.io NFL response:
            # {"hdp": -3.5, "home": "1.962", "away": "1.847"}
            # hdp is the HOME spread. The away spread is its inverse.
            for row in rows:
                raw_home_line = first_number(
                    row,
                    "hdp",
                    "line",
                    "point",
                )
                direct_away_price = first_number(
                    row,
                    "away",
                )
                direct_home_price = first_number(
                    row,
                    "home",
                )

                if (
                    raw_home_line is not None
                    and direct_away_price is not None
                    and direct_home_price is not None
                ):
                    home_line = raw_home_line
                    away_line = -raw_home_line
                    away_price = decimal_to_american(
                        direct_away_price
                    )
                    home_price = decimal_to_american(
                        direct_home_price
                    )
                    break

            if (
                away_line is not None
                and home_line is not None
            ):
                output["spread"] = {
                    "away": away_line,
                    "home": home_line,
                    "away_price": away_price,
                    "home_price": home_price,
                }

        # -------------------------
        # GAME TOTAL
        # -------------------------

        elif key in {
            "totals",
            "total",
            "over under",
            "over/under",
        }:
            row = balanced_two_way_row(
                rows
            )

            if row is not None:
                line = first_number(
                    row,
                    "hdp",
                    "line",
                    "point",
                )
                over_decimal = first_number(
                    row,
                    "over",
                    "overOdds",
                    "over_odds",
                )
                under_decimal = first_number(
                    row,
                    "under",
                    "underOdds",
                    "under_odds",
                )

                if line is not None:
                    output["game_total"] = {
                        "line": line,
                        "over_price": decimal_to_american(
                            over_decimal
                        ),
                        "under_price": decimal_to_american(
                            under_decimal
                        ),
                    }

        # -------------------------
        # POSTED TEAM TOTALS
        # -------------------------

        elif key in {
            "team total home",
            "team total points home",
        }:
            row = balanced_two_way_row(
                rows
            )

            if row is not None:
                output.setdefault(
                    "team_total",
                    {},
                )["home"] = {
                    "line": first_number(
                        row,
                        "hdp",
                        "line",
                        "point",
                    ),
                    "over_price": decimal_to_american(
                        first_number(
                            row,
                            "over",
                            "overOdds",
                            "over_odds",
                        )
                    ),
                    "under_price": decimal_to_american(
                        first_number(
                            row,
                            "under",
                            "underOdds",
                            "under_odds",
                        )
                    ),
                }

        elif key in {
            "team total away",
            "team total points away",
        }:
            row = balanced_two_way_row(
                rows
            )

            if row is not None:
                output.setdefault(
                    "team_total",
                    {},
                )["away"] = {
                    "line": first_number(
                        row,
                        "hdp",
                        "line",
                        "point",
                    ),
                    "over_price": decimal_to_american(
                        first_number(
                            row,
                            "over",
                            "overOdds",
                            "over_odds",
                        )
                    ),
                    "under_price": decimal_to_american(
                        first_number(
                            row,
                            "under",
                            "underOdds",
                            "under_odds",
                        )
                    ),
                }

    return output

PROP_MARKET_MAP = {
    "passing yards": "passing_yards",
    "pass yards": "passing_yards",

    "passing touchdowns": "passing_touchdowns",
    "passing tds": "passing_touchdowns",

    "passing attempts": "passing_attempts",

    "passing completions": "passing_completions",
    "completions": "passing_completions",

    "passing interceptions": "interceptions",
    "interceptions thrown": "interceptions",

    "rushing yards": "rushing_yards",
    "rush yards": "rushing_yards",

    "rushing attempts": "rushing_attempts",
    "rush attempts": "rushing_attempts",
    "carries": "rushing_attempts",

    "receptions": "receptions",

    "receiving yards": "receiving_yards",
    "reception yards": "receiving_yards",

    "longest reception": "longest_reception",
    "reception longest": "longest_reception",

    "longest rush": "longest_rush",
    "rush longest": "longest_rush",

    "anytime touchdown": "anytime_touchdown",
    "anytime td": "anytime_touchdown",
    "anytime touchdown scorer": "anytime_touchdown",
}


def identify_prop_type(
    name: str,
) -> str | None:
    key = (
        name.lower()
        .replace("-", " ")
        .replace("_", " ")
    )

    for phrase, prop_type in (
        PROP_MARKET_MAP.items()
    ):
        if phrase in key:
            return prop_type

    return None


def normalize_player_props(
    bookmaker: str,
    markets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    props = []

    for market in markets:
        name = market_name(
            market
        )

        prop_type = identify_prop_type(
            name
        )

        if not prop_type:
            continue

        for row in odds_rows(
            market
        ):
            player_name = clean_text(
                row.get("label")
                or row.get("player")
                or row.get("name")
            )

            if not player_name:
                continue

            line = first_number(
                row,
                "hdp",
                "line",
                "point",
            )

            # Odds-API.io returns sportsbook prices
            # as DECIMAL odds. Normalize every player
            # prop price to American odds here so all
            # downstream files use one consistent format.
            over_decimal = first_number(
                row,
                "over",
                "overOdds",
                "over_odds",
            )

            under_decimal = first_number(
                row,
                "under",
                "underOdds",
                "under_odds",
            )

            yes_decimal = first_number(
                row,
                "yes",
                "yesOdds",
                "yes_odds",
            )

            no_decimal = first_number(
                row,
                "no",
                "noOdds",
                "no_odds",
            )

            # Anytime TD markets may expose the YES price
            # as a generic odds/price/value field instead
            # of an explicit yes field.
            if (
                prop_type
                == "anytime_touchdown"
                and yes_decimal is None
            ):
                yes_decimal = first_number(
                    row,
                    "odds",
                    "price",
                    "value",
                )

            over_odds = (
                decimal_to_american(
                    over_decimal
                )
                if over_decimal is not None
                else None
            )

            under_odds = (
                decimal_to_american(
                    under_decimal
                )
                if under_decimal is not None
                else None
            )

            yes_odds = (
                decimal_to_american(
                    yes_decimal
                )
                if yes_decimal is not None
                else None
            )

            no_odds = (
                decimal_to_american(
                    no_decimal
                )
                if no_decimal is not None
                else None
            )

            props.append(
                {
                    "player_name": (
                        player_name
                    ),
                    "prop_type": (
                        prop_type
                    ),
                    "market_name": (
                        name
                    ),
                    "line": line,
                    "over_odds": (
                        over_odds
                    ),
                    "under_odds": (
                        under_odds
                    ),
                    "yes_odds": (
                        yes_odds
                    ),
                    "no_odds": (
                        no_odds
                    ),
                    "sportsbook": (
                        bookmaker
                    ),
                    "source": (
                        "odds_api_io"
                    ),
                }
            )

    return props


def normalize_event_odds(
    event: dict[str, Any],
    slate_game: dict[str, Any],
    odds_payload: dict[str, Any],
) -> dict[str, Any]:
    away_name = clean_text(
        odds_payload.get("away")
        or event.get("away")
    )

    home_name = clean_text(
        odds_payload.get("home")
        or event.get("home")
    )

    normalized_books = []

    all_props = []

    for bookmaker, markets in bookmaker_items(
        odds_payload
    ):
        featured = (
            normalize_featured_markets(
                bookmaker,
                markets,
                away_name,
                home_name,
            )
        )

        props = (
            normalize_player_props(
                bookmaker,
                markets,
            )
        )

        if featured:
            normalized_books.append(
                {
                    "key": bookmaker,
                    "title": bookmaker,
                    "markets": featured,
                }
            )

        all_props.extend(
            props
        )

    normalized_books.sort(
        key=lambda book: BOOKMAKER_PRIORITY.get(
            clean_text(book.get("key")).lower(),
            len(BOOKMAKER_PRIORITY),
        )
    )

    return {
        "event_id": (
            odds_payload.get("id")
            or event.get("id")
        ),
        "game_id": (
            slate_game.get(
                "game_id"
            )
        ),
        "season": (
            slate_game.get(
                "season"
            )
        ),
        "week": (
            slate_game.get(
                "week"
            )
        ),
        "game_type": (
            slate_game.get(
                "game_type"
            )
        ),
        "game_date": (
            slate_game.get(
                "game_date"
            )
        ),
        "game_time": (
            slate_game.get(
                "game_time"
            )
        ),
        "commence_time": (
            odds_payload.get("date")
            or event.get("date")
        ),
        "away_team": (
            normalize_team(
                away_name
            )
        ),
        "home_team": (
            normalize_team(
                home_name
            )
        ),
        "bookmakers": (
            normalized_books
        ),
        "player_props": (
            all_props
        ),
    }


# =========================================================
# FETCH EVENT ODDS
# =========================================================

def fetch_event_odds(
    event_id: Any,
) -> dict[str, Any]:
    payload = api_get(
        "odds",
        {
            "apiKey": API_KEY,
            "eventId": event_id,
            "bookmakers": ",".join(
                BOOKMAKERS
            ),
        },
    )

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            f"Unexpected Odds-API.io odds "
            f"response for event "
            f"{event_id}."
        )

    return payload


# =========================================================
# BUILD
# =========================================================

def build_for_slate(
    slate_payload: Any,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    matched = match_events_to_slate(
        events,
        slate_payload,
    )

    games = []
    failures = 0

    for event, slate_game in matched:
        event_id = event.get(
            "id"
        )

        if event_id is None:
            continue

        try:
            odds_payload = (
                fetch_event_odds(
                    event_id
                )
            )

            games.append(
                normalize_event_odds(
                    event,
                    slate_game,
                    odds_payload,
                )
            )

        except RuntimeError as exc:
            failures += 1

            print(
                f"   ⚠️ Odds unavailable for "
                f"{event.get('away')} @ "
                f"{event.get('home')}: "
                f"{exc}"
            )

    return {
        "generated_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "provider": (
            "odds_api_io"
        ),
        "base_url": (
            BASE_URL
        ),
        "sport": (
            SPORT
        ),
        "league": (
            LEAGUE
        ),
        "bookmaker_preference": (
            BOOKMAKERS
        ),
        "games": (
            games
        ),
        "counts": {
            "matched_events": len(
                matched
            ),
            "games": len(
                games
            ),
            "failed_events": (
                failures
            ),
            "player_props": sum(
                len(
                    game.get(
                        "player_props",
                        [],
                    )
                )
                for game in games
            ),
        },
    }


def save_live_output(
    payload: dict[str, Any],
    output_file: Path,
    web_output_file: Path,
) -> bool:
    existing = load_json(
        output_file,
        default={},
    )

    if (
        not payload.get("games")
        and isinstance(
            existing,
            dict,
        )
        and existing.get("games")
    ):
        print(
            "   ⚠️ Odds-API.io returned "
            "zero matched games. "
            f"Preserving existing "
            f"{output_file.name}."
        )

        return False

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

    return True


def build_nfl_odds():
    print(
        "\n📡 BUILDING LIVE "
        "NFL ODDS\n"
    )

    if not API_KEY:
        raise RuntimeError(
            "Missing ODDS_API_IO_KEY. "
            "Set it in your environment "
            "before running "
            "providers.nfl_odds."
        )

    if not SLATE_FILE.exists():
        raise RuntimeError(
            f"NFL slate not found: "
            f"{SLATE_FILE}"
        )

    events = fetch_events()

    print(
        f"   Odds-API.io events: "
        f"{len(events)}"
    )

    current_slate = load_json(
        SLATE_FILE,
        default={},
    )

    current_output = (
        build_for_slate(
            current_slate,
            events,
        )
    )

    print(
        "\n   Current slate"
    )

    save_live_output(
        current_output,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
    )

    print(
        f"   ✅ "
        f"{current_output['counts']['games']} "
        f"live market games"
    )

    print(
        f"   ✅ "
        f"{current_output['counts']['player_props']} "
        f"player prop rows"
    )

    print(
        f"      {OUTPUT_FILE}"
    )

    print(
        f"      {WEB_OUTPUT_FILE}"
    )

    if NEXT_SLATE_FILE.exists():
        next_slate = load_json(
            NEXT_SLATE_FILE,
            default={},
        )

        next_output = (
            build_for_slate(
                next_slate,
                events,
            )
        )

        print(
            "\n   Next slate"
        )

        save_live_output(
            next_output,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
        )

        print(
            f"   ✅ "
            f"{next_output['counts']['games']} "
            f"live market games"
        )

        print(
            f"   ✅ "
            f"{next_output['counts']['player_props']} "
            f"player prop rows"
        )

        print(
            f"      {NEXT_OUTPUT_FILE}"
        )

        print(
            f"      "
            f"{NEXT_WEB_OUTPUT_FILE}"
        )

    print(
        "\n✅ LIVE NFL ODDS "
        "COMPLETE\n"
    )

    return True


if __name__ == "__main__":
    build_nfl_odds()
