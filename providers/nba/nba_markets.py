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


# ============================================================
# CONFIG
# ============================================================

MODEL_ROOT = Path(__file__).resolve().parents[2]

NBA_DIR = (
    MODEL_ROOT
    / "data"
    / "processed"
    / "nba"
)

WEB_NBA_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nba"
)

OUTPUT_FILE = (
    NBA_DIR
    / "market_history.json"
)

WEB_OUTPUT_FILE = (
    WEB_NBA_DIR
    / "market_history.json"
)

API_KEY = os.getenv(
    "ODDS_API_IO_KEY"
)

BASE_URL = os.getenv(
    "ODDS_API_IO_BASE",
    "https://api.odds-api.io/v3",
).rstrip("/")

SPORT = os.getenv(
    "NBA_ODDS_API_IO_SPORT",
    "basketball",
)

LEAGUE = os.getenv(
    "NBA_ODDS_API_IO_LEAGUE",
    "usa-nba",
)

BOOKMAKERS = [
    value.strip()
    for value in os.getenv(
        "NBA_ODDS_API_IO_BOOKMAKERS",
        "FanDuel,DraftKings",
    ).split(",")
    if value.strip()
]

CURRENT_SEASON = "2026-27"
LAST_SEASON = "2025-26"

# Last completed NBA regular season.
HISTORY_FROM = os.getenv(
    "NBA_MARKET_HISTORY_FROM",
    "2025-10-01T00:00:00Z",
)

HISTORY_TO = os.getenv(
    "NBA_MARKET_HISTORY_TO",
    "2026-04-20T23:59:59Z",
)

MARKETS = "Spread,Totals"

# Leave room under the free-plan hourly request allowance
# for event discovery and any other Odds-API.io calls.
MAX_ODDS_REQUESTS = int(
    os.getenv(
        "NBA_MARKET_MAX_ODDS_REQUESTS",
        "80",
    )
)

# Historical event discovery is split into smaller date windows.
HISTORY_WINDOW_DAYS = 30


# ============================================================
# TEAM NORMALIZATION
# ============================================================

TEAM_ALIASES = {
    "Atlanta Hawks": "ATL",
    "Boston Celtics": "BOS",
    "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI",
    "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL",
    "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW",
    "Houston Rockets": "HOU",
    "Indiana Pacers": "IND",
    "LA Clippers": "LAC",
    "Los Angeles Clippers": "LAC",
    "Los Angeles Lakers": "LAL",
    "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA",
    "Milwaukee Bucks": "MIL",
    "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP",
    "New York Knicks": "NYK",
    "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL",
    "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR",
    "Sacramento Kings": "SAC",
    "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR",
    "Utah Jazz": "UTA",
    "Washington Wizards": "WAS",
}

ABBREVIATION_ALIASES = {
    "NO": "NOP",
    "NY": "NYK",
    "SA": "SAS",
    "GS": "GSW",
    "UTAH": "UTA",
}


def clean_text(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def normalize_team(
    value: Any,
) -> str:
    text = clean_text(
        value
    )

    if text in TEAM_ALIASES:
        return TEAM_ALIASES[
            text
        ]

    upper = text.upper()

    return ABBREVIATION_ALIASES.get(
        upper,
        upper,
    )


# ============================================================
# GENERIC HELPERS
# ============================================================

def number(
    value: Any,
) -> float | None:
    try:
        if value in (
            None,
            "",
        ):
            return None

        return float(
            value
        )

    except Exception:
        return None


def safe_int(
    value: Any,
) -> int | None:
    try:
        if value in (
            None,
            "",
        ):
            return None

        return int(
            float(value)
        )

    except Exception:
        return None


def write_json(
    path: Path,
    payload: dict[str, Any],
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
) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            payload = json.load(
                handle
            )

        if isinstance(
            payload,
            dict,
        ):
            return payload

    except Exception:
        pass

    return None


def parse_datetime(
    value: str,
) -> datetime:
    text = (
        value
        .strip()
    )

    if text.endswith("Z"):
        text = (
            text[:-1]
            + "+00:00"
        )

    parsed = (
        datetime
        .fromisoformat(
            text
        )
    )

    if parsed.tzinfo is None:
        parsed = (
            parsed.replace(
                tzinfo=timezone.utc
            )
        )

    return (
        parsed
        .astimezone(
            timezone.utc
        )
    )


def iso_z(
    value: datetime,
) -> str:
    return (
        value
        .astimezone(
            timezone.utc
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


# ============================================================
# HTTP
# ============================================================

def api_get(
    endpoint: str,
    params: dict[str, Any],
) -> Any:
    query = urlencode(
        {
            key: value
            for key, value
            in params.items()
            if value not in (
                None,
                "",
            )
        }
    )

    url = (
        f"{BASE_URL}/"
        f"{endpoint.lstrip('/')}?"
        f"{query}"
    )

    request = Request(
        url,
        headers={
            "Accept": (
                "application/json"
            ),
            "User-Agent": (
                "Alpha-Wagerz/1.0"
            ),
        },
    )

    try:
        with urlopen(
            request,
            timeout=60,
        ) as response:
            raw = (
                response.read()
            )

            encoding = (
                response.headers
                .get(
                    "Content-Encoding",
                    "",
                )
                .lower()
            )

            if (
                "gzip" in encoding
                or raw[:2]
                == b"\x1f\x8b"
            ):
                raw = (
                    gzip.decompress(
                        raw
                    )
                )

            return json.loads(
                raw.decode(
                    "utf-8"
                )
            )

    except HTTPError as exc:
        body = (
            exc.read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

        raise RuntimeError(
            "Odds-API.io returned HTTP "
            f"{exc.code}: "
            f"{body[:1000]}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            "Unable to reach "
            "Odds-API.io: "
            f"{exc}"
        ) from exc


# ============================================================
# RESPONSE HELPERS
# ============================================================

def response_events(
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
        for key in (
            "events",
            "data",
            "results",
        ):
            rows = (
                payload.get(
                    key
                )
            )

            if isinstance(
                rows,
                list,
            ):
                return [
                    row
                    for row
                    in rows
                    if isinstance(
                        row,
                        dict,
                    )
                ]

    return []


def response_object(
    payload: Any,
) -> dict[str, Any]:
    if not isinstance(
        payload,
        dict,
    ):
        return {}

    for key in (
        "data",
        "result",
        "event",
    ):
        value = (
            payload.get(
                key
            )
        )

        if isinstance(
            value,
            dict,
        ):
            return value

    return payload


# ============================================================
# MARKET PARSING
# ============================================================

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
        .replace(
            "-",
            " ",
        )
        .replace(
            "_",
            " ",
        )
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
            row.get(
                key
            )
        )

        if value is not None:
            return value

    return None


def balanced_two_way_row(
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = []

    for index, row in enumerate(
        rows
    ):
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

        over_probability = (
            1.0 / over
        )

        under_probability = (
            1.0 / under
        )

        balance = abs(
            over_probability
            - under_probability
        )

        distance_from_even = (
            abs(
                over - 2.0
            )
            + abs(
                under - 2.0
            )
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

    return candidates[
        0
    ][3]


def parse_spread(
    markets: list[dict[str, Any]],
) -> tuple[
    float | None,
    float | None,
]:
    """
    Odds-API.io Spread hdp is from
    the HOME perspective.

    hdp = -4.5 means:
        HOME -4.5
        AWAY +4.5
    """

    for market in markets:
        if market_key(
            market
        ) not in {
            "spread",
            "handicap",
        }:
            continue

        rows = odds_rows(
            market
        )

        if not rows:
            continue

        candidates = []

        for index, row in enumerate(
            rows
        ):
            home_line = (
                first_number(
                    row,
                    "hdp",
                    "line",
                    "point",
                )
            )

            home_price = (
                first_number(
                    row,
                    "home",
                )
            )

            away_price = (
                first_number(
                    row,
                    "away",
                )
            )

            if home_line is None:
                continue

            if (
                home_price
                is not None
                and away_price
                is not None
                and home_price > 1.0
                and away_price > 1.0
            ):
                balance = abs(
                    (1.0 / home_price)
                    - (
                        1.0
                        / away_price
                    )
                )

                distance = (
                    abs(
                        home_price
                        - 2.0
                    )
                    + abs(
                        away_price
                        - 2.0
                    )
                )

            else:
                balance = 999.0
                distance = 999.0

            candidates.append(
                (
                    balance,
                    distance,
                    index,
                    home_line,
                )
            )

        if candidates:
            candidates.sort(
                key=lambda item: (
                    item[0],
                    item[1],
                    item[2],
                )
            )

            home_spread = (
                candidates[
                    0
                ][3]
            )

            return (
                -home_spread,
                home_spread,
            )

    return (
        None,
        None,
    )


def parse_total(
    markets: list[dict[str, Any]],
) -> float | None:
    for market in markets:
        if market_key(
            market
        ) not in {
            "totals",
            "total",
            "over under",
            "over/under",
        }:
            continue

        row = (
            balanced_two_way_row(
                odds_rows(
                    market
                )
            )
        )

        if row is None:
            continue

        return first_number(
            row,
            "hdp",
            "line",
            "point",
        )

    return None


# ============================================================
# SCORE PARSING
# ============================================================

def extract_scores(
    event: dict[str, Any],
) -> tuple[
    int | None,
    int | None,
]:
    scores = event.get(
        "scores",
        {},
    )

    if not isinstance(
        scores,
        dict,
    ):
        return (
            None,
            None,
        )

    periods = scores.get(
        "periods",
        {},
    )

    if isinstance(
        periods,
        dict,
    ):
        full_time = (
            periods.get("ft")
            or periods.get(
                "full_time"
            )
        )

        if isinstance(
            full_time,
            dict,
        ):
            home = safe_int(
                full_time.get(
                    "home"
                )
            )

            away = safe_int(
                full_time.get(
                    "away"
                )
            )

            if (
                home is not None
                and away is not None
            ):
                return (
                    away,
                    home,
                )

    home = safe_int(
        scores.get(
            "home"
        )
    )

    away = safe_int(
        scores.get(
            "away"
        )
    )

    return (
        away,
        home,
    )


# ============================================================
# BOOKMAKER SELECTION
# ============================================================

def bookmaker_markets(
    event: dict[str, Any],
) -> tuple[
    str | None,
    list[dict[str, Any]],
]:
    raw = event.get(
        "bookmakers",
        {},
    )

    if not isinstance(
        raw,
        dict,
    ):
        return (
            None,
            [],
        )

    # FanDuel first, then DraftKings.
    for preferred in BOOKMAKERS:
        for (
            bookmaker,
            markets,
        ) in raw.items():
            if (
                clean_text(
                    bookmaker
                ).lower()
                != preferred.lower()
            ):
                continue

            if isinstance(
                markets,
                list,
            ):
                return (
                    bookmaker,
                    [
                        market
                        for market
                        in markets
                        if isinstance(
                            market,
                            dict,
                        )
                    ],
                )

    # Do not silently substitute
    # another sportsbook.
    return (
        None,
        [],
    )


# ============================================================
# EVENT HELPERS
# ============================================================

def event_id(
    event: dict[str, Any],
) -> str:
    return clean_text(
        event.get("id")
        or event.get(
            "eventId"
        )
        or event.get(
            "event_id"
        )
    )


def event_date(
    event: dict[str, Any],
) -> str:
    return clean_text(
        event.get("date")
        or event.get(
            "commence_time"
        )
        or event.get(
            "commenceTime"
        )
        or event.get(
            "start_time"
        )
        or event.get(
            "startTime"
        )
    )


def event_away_team(
    event: dict[str, Any],
) -> str:
    return clean_text(
        event.get("away")
        or event.get(
            "away_team"
        )
        or event.get(
            "awayTeam"
        )
    )


def event_home_team(
    event: dict[str, Any],
) -> str:
    return clean_text(
        event.get("home")
        or event.get(
            "home_team"
        )
        or event.get(
            "homeTeam"
        )
    )


# ============================================================
# ODDS PAYLOAD MERGING
# ============================================================

def merge_event_and_odds(
    event: dict[str, Any],
    odds_payload: Any,
) -> dict[str, Any]:
    merged = dict(
        event
    )

    odds_object = (
        response_object(
            odds_payload
        )
    )

    for (
        key,
        value,
    ) in odds_object.items():
        merged[
            key
        ] = value

    # Preserve identifying information
    # from the historical event response
    # if the odds response does not include it.
    if not event_id(
        merged
    ):
        merged["id"] = (
            event_id(
                event
            )
        )

    if not event_date(
        merged
    ):
        merged["date"] = (
            event_date(
                event
            )
        )

    if not event_away_team(
        merged
    ):
        merged["away"] = (
            event_away_team(
                event
            )
        )

    if not event_home_team(
        merged
    ):
        merged["home"] = (
            event_home_team(
                event
            )
        )

    return merged


# ============================================================
# NORMALIZE EVENT
# ============================================================

def normalize_event(
    event: dict[str, Any],
) -> dict[str, Any] | None:
    away_team = normalize_team(
        event_away_team(
            event
        )
    )

    home_team = normalize_team(
        event_home_team(
            event
        )
    )

    if (
        not away_team
        or not home_team
    ):
        return None

    (
        away_score,
        home_score,
    ) = extract_scores(
        event
    )

    bookmaker, markets = (
        bookmaker_markets(
            event
        )
    )

    (
        away_spread,
        home_spread,
    ) = parse_spread(
        markets
    )

    total = parse_total(
        markets
    )

    return {
        "event_id": (
            event_id(
                event
            )
        ),
        "date": (
            event_date(
                event
            )
        ),
        "status": (
            event.get(
                "status"
            )
        ),
        "away_team": (
            away_team
        ),
        "home_team": (
            home_team
        ),
        "away_score": (
            away_score
        ),
        "home_score": (
            home_score
        ),
        "bookmaker": (
            bookmaker
        ),
        "away_spread": (
            round(
                away_spread,
                2,
            )
            if away_spread
            is not None
            else None
        ),
        "home_spread": (
            round(
                home_spread,
                2,
            )
            if home_spread
            is not None
            else None
        ),
        "total": (
            round(
                total,
                2,
            )
            if total
            is not None
            else None
        ),
    }


# ============================================================
# HISTORICAL DATE WINDOWS
# ============================================================

def history_windows() -> list[
    tuple[str, str]
]:
    start = parse_datetime(
        HISTORY_FROM
    )

    end = parse_datetime(
        HISTORY_TO
    )

    windows: list[
        tuple[str, str]
    ] = []

    current = start

    while current <= end:
        window_end = min(
            current
            + timedelta(
                days=HISTORY_WINDOW_DAYS
            ),
            end,
        )

        windows.append(
            (
                iso_z(
                    current
                ),
                iso_z(
                    window_end
                ),
            )
        )

        current = (
            window_end
            + timedelta(
                seconds=1
            )
        )

    return windows


# ============================================================
# HISTORICAL EVENTS
# ============================================================

def fetch_historical_events() -> list[
    dict[str, Any]
]:
    all_events: dict[
        str,
        dict[str, Any],
    ] = {}

    windows = (
        history_windows()
    )

    for (
        index,
        (
            window_from,
            window_to,
        ),
    ) in enumerate(
        windows,
        start=1,
    ):
        print(
            "Fetching NBA historical "
            "events "
            f"{index}/{len(windows)} "
            f"({window_from[:10]} -> "
            f"{window_to[:10]})...",
            flush=True,
        )

        payload = api_get(
            "historical/events",
            {
                "apiKey": (
                    API_KEY
                ),
                "sport": (
                    SPORT
                ),
                "league": (
                    LEAGUE
                ),
                "from": (
                    window_from
                ),
                "to": (
                    window_to
                ),
            },
        )

        rows = response_events(
            payload
        )

        print(
            f"   received "
            f"{len(rows):,} events",
            flush=True,
        )

        for event in rows:
            identifier = (
                event_id(
                    event
                )
            )

            if not identifier:
                continue

            all_events[
                identifier
            ] = event

    events = list(
        all_events.values()
    )

    events.sort(
        key=lambda event: (
            event_date(
                event
            ),
            event_id(
                event
            ),
        )
    )

    return events


# ============================================================
# HISTORICAL ODDS
# ============================================================

def fetch_historical_odds(
    identifier: str,
) -> Any:
    return api_get(
        "historical/odds",
        {
            "apiKey": (
                API_KEY
            ),
            "eventId": (
                identifier
            ),
            "bookmakers": (
                ",".join(
                    BOOKMAKERS
                )
            ),
            "markets": (
                MARKETS
            ),
        },
    )


# ============================================================
# EXISTING HISTORY
# ============================================================

def load_existing_payload() -> (
    dict[str, Any] | None
):
    existing = load_json(
        OUTPUT_FILE
    )

    if existing is None:
        existing = load_json(
            WEB_OUTPUT_FILE
        )

    return existing


def existing_games_by_id() -> dict[
    str,
    dict[str, Any],
]:
    payload = (
        load_existing_payload()
    )

    if not payload:
        return {}

    games = payload.get(
        "games",
        [],
    )

    if not isinstance(
        games,
        list,
    ):
        return {}

    result: dict[
        str,
        dict[str, Any],
    ] = {}

    for game in games:
        if not isinstance(
            game,
            dict,
        ):
            continue

        identifier = clean_text(
            game.get(
                "event_id"
            )
        )

        if not identifier:
            continue

        result[
            identifier
        ] = game

    return result


def game_has_spread(
    game: dict[str, Any],
) -> bool:
    return (
        game.get(
            "away_spread"
        )
        is not None
        and game.get(
            "home_spread"
        )
        is not None
    )


def game_has_total(
    game: dict[str, Any],
) -> bool:
    return (
        game.get(
            "total"
        )
        is not None
    )


def game_has_market_data(
    game: dict[str, Any],
) -> bool:
    return (
        game_has_spread(
            game
        )
        and game_has_total(
            game
        )
    )


# ============================================================
# FALLBACK
# ============================================================

def preserve_existing() -> bool:
    existing = (
        load_existing_payload()
    )

    if not existing:
        return False

    games = existing.get(
        "games"
    )

    if not isinstance(
        games,
        list,
    ) or not games:
        return False

    write_json(
        OUTPUT_FILE,
        existing,
    )

    write_json(
        WEB_OUTPUT_FILE,
        existing,
    )

    print(
        "Preserved last-known-good "
        "NBA market history.",
        flush=True,
    )

    return True


# ============================================================
# BUILD OUTPUT
# ============================================================

def build_payload(
    games: list[
        dict[str, Any]
    ],
    historical_event_count: int,
    fetched_this_run: int,
    failed_this_run: int,
) -> dict[str, Any]:
    games.sort(
        key=lambda game: (
            clean_text(
                game.get(
                    "date"
                )
            ),
            clean_text(
                game.get(
                    "away_team"
                )
            ),
            clean_text(
                game.get(
                    "home_team"
                )
            ),
        )
    )

    completed_games = [
        game
        for game in games
        if (
            game.get(
                "away_score"
            )
            is not None
            and game.get(
                "home_score"
            )
            is not None
        )
    ]

    spread_games = [
        game
        for game
        in completed_games
        if game_has_spread(
            game
        )
    ]

    total_games = [
        game
        for game
        in completed_games
        if game_has_total(
            game
        )
    ]

    complete_market_games = [
        game
        for game
        in completed_games
        if game_has_market_data(
            game
        )
    ]

    return {
        "generated_at": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "provider": (
            "odds_api_io"
        ),
        "source": (
            "historical_events_and_odds"
        ),
        "sport": (
            SPORT
        ),
        "league": (
            LEAGUE
        ),
        "season": (
            LAST_SEASON
        ),
        "season_type": (
            "Regular Season"
        ),
        "from": (
            HISTORY_FROM
        ),
        "to": (
            HISTORY_TO
        ),
        "bookmaker_preference": (
            BOOKMAKERS
        ),
        "markets": [
            "Spread",
            "Totals",
        ],
        "incremental": True,
        "max_odds_requests_per_run": (
            MAX_ODDS_REQUESTS
        ),
        "games": (
            games
        ),
        "counts": {
            "historical_events": (
                historical_event_count
            ),
            "games": (
                len(
                    games
                )
            ),
            "completed_games": (
                len(
                    completed_games
                )
            ),
            "spread_games": (
                len(
                    spread_games
                )
            ),
            "total_games": (
                len(
                    total_games
                )
            ),
            "complete_market_games": (
                len(
                    complete_market_games
                )
            ),
            "odds_fetched_this_run": (
                fetched_this_run
            ),
            "odds_failed_this_run": (
                failed_this_run
            ),
        },
    }


def save_payload(
    payload: dict[str, Any],
) -> None:
    write_json(
        OUTPUT_FILE,
        payload,
    )

    write_json(
        WEB_OUTPUT_FILE,
        payload,
    )


# ============================================================
# BUILD
# ============================================================

def build_nba_markets() -> bool:
    print(
        "\nBUILDING NBA MARKET HISTORY\n",
        flush=True,
    )

    if not API_KEY:
        raise RuntimeError(
            "Missing ODDS_API_IO_KEY. "
            "The GitHub Actions workflow "
            "provides this secret; for a "
            "local run, load the same key "
            "into the environment."
        )

    existing = (
        existing_games_by_id()
    )

    print(
        "Existing historical games: "
        f"{len(existing):,}",
        flush=True,
    )

    try:
        historical_events = (
            fetch_historical_events()
        )

    except Exception as exc:
        print(
            "NBA historical event "
            "fetch failed: "
            f"{exc}",
            flush=True,
        )

        if preserve_existing():
            return False

        raise

    if not historical_events:
        print(
            "Odds-API.io returned zero "
            "NBA historical events.",
            flush=True,
        )

        if preserve_existing():
            return False

        raise RuntimeError(
            "No NBA historical events "
            "were returned."
        )

    print(
        "\nHistorical NBA events found: "
        f"{len(historical_events):,}",
        flush=True,
    )

    missing_events: list[
        dict[str, Any]
    ] = []

    for event in historical_events:
        identifier = (
            event_id(
                event
            )
        )

        if not identifier:
            continue

        saved = existing.get(
            identifier
        )

        if (
            saved is not None
            and game_has_market_data(
                saved
            )
        ):
            continue

        missing_events.append(
            event
        )

    print(
        "Events still needing odds:   "
        f"{len(missing_events):,}",
        flush=True,
    )

    batch = (
        missing_events[
            :MAX_ODDS_REQUESTS
        ]
    )

    print(
        "Odds requests this run:      "
        f"{len(batch):,} / "
        f"{MAX_ODDS_REQUESTS:,}",
        flush=True,
    )

    fetched = 0
    failed = 0

    for (
        index,
        event,
    ) in enumerate(
        batch,
        start=1,
    ):
        identifier = (
            event_id(
                event
            )
        )

        away = (
            event_away_team(
                event
            )
        )

        home = (
            event_home_team(
                event
            )
        )

        print(
            f"[{index}/{len(batch)}] "
            f"{away} @ {home} "
            f"(event {identifier})",
            flush=True,
        )

        try:
            odds_payload = (
                fetch_historical_odds(
                    identifier
                )
            )

            merged = (
                merge_event_and_odds(
                    event,
                    odds_payload,
                )
            )

            normalized = (
                normalize_event(
                    merged
                )
            )

            if normalized is None:
                failed += 1

                print(
                    "   skipped: unable "
                    "to normalize event",
                    flush=True,
                )

                continue

            existing[
                identifier
            ] = normalized

            fetched += 1

            spread = (
                normalized.get(
                    "home_spread"
                )
            )

            total = (
                normalized.get(
                    "total"
                )
            )

            bookmaker = (
                normalized.get(
                    "bookmaker"
                )
            )

            print(
                "   saved: "
                f"{bookmaker or 'no preferred book'}"
                " | "
                f"spread={spread}"
                " | "
                f"total={total}",
                flush=True,
            )

        except Exception as exc:
            failed += 1

            print(
                "   failed: "
                f"{exc}",
                flush=True,
            )

    # Preserve every discovered event in the
    # database even if its historical odds have
    # not been fetched yet. This means future
    # runs can continue filling the same history.
    for event in historical_events:
        identifier = (
            event_id(
                event
            )
        )

        if (
            not identifier
            or identifier in existing
        ):
            continue

        normalized = (
            normalize_event(
                event
            )
        )

        if normalized is None:
            continue

        existing[
            identifier
        ] = normalized

    games = list(
        existing.values()
    )

    payload = build_payload(
        games=games,
        historical_event_count=(
            len(
                historical_events
            )
        ),
        fetched_this_run=(
            fetched
        ),
        failed_this_run=(
            failed
        ),
    )

    save_payload(
        payload
    )

    counts = (
        payload[
            "counts"
        ]
    )

    remaining = max(
        0,
        len(
            missing_events
        )
        - len(
            batch
        ),
    )

    print(
        "\nNBA MARKET HISTORY UPDATED",
        flush=True,
    )

    print(
        "Historical events:        "
        f"{counts['historical_events']:,}",
        flush=True,
    )

    print(
        "Stored games:             "
        f"{counts['games']:,}",
        flush=True,
    )

    print(
        "Completed games:          "
        f"{counts['completed_games']:,}",
        flush=True,
    )

    print(
        "Games with spreads:       "
        f"{counts['spread_games']:,}",
        flush=True,
    )

    print(
        "Games with totals:        "
        f"{counts['total_games']:,}",
        flush=True,
    )

    print(
        "Complete market games:    "
        f"{counts['complete_market_games']:,}",
        flush=True,
    )

    print(
        "Odds fetched this run:    "
        f"{fetched:,}",
        flush=True,
    )

    print(
        "Odds failures this run:   "
        f"{failed:,}",
        flush=True,
    )

    print(
        "Remaining after this run: "
        f"{remaining:,}",
        flush=True,
    )

    print(
        "Model output:             "
        f"{OUTPUT_FILE}",
        flush=True,
    )

    print(
        "Website output:           "
        f"{WEB_OUTPUT_FILE}",
        flush=True,
    )

    return True


def main() -> None:
    build_nba_markets()


if __name__ == "__main__":
    main()