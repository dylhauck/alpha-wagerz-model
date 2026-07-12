import os
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

from utils.json_utils import load_json, save_json
from utils.player_name import normalize_player_name


load_dotenv(dotenv_path=Path.cwd() / ".env")

API_KEY = os.getenv("ODDS_API_IO_KEY")
BASE_URL = os.getenv(
    "ODDS_API_IO_BASE",
    "https://api.odds-api.io/v3",
).rstrip("/")

MARKET_TIMEZONE = os.getenv(
    "MARKET_TIMEZONE",
    "America/Chicago",
)

ALL_GAMES_FILE = Path("data/processed/all_games.json")
OUTPUT_FILE = Path("data/processed/market_lines.json")
CACHE_DIR = Path("data/cache/markets")
CACHE_FILE = CACHE_DIR / "latest_market_lines.json"

BOOKMAKERS = ["FanDuel", "DraftKings"]
REQUEST_TIMEOUT = 45

TEAM_ALIASES = {
    "athletics": "oakland athletics",
    "oakland athletics": "oakland athletics",
    "the athletics": "oakland athletics",
    "la dodgers": "los angeles dodgers",
    "los angeles dodgers": "los angeles dodgers",
    "la angels": "los angeles angels",
    "los angeles angels": "los angeles angels",
    "sf giants": "san francisco giants",
    "san francisco giants": "san francisco giants",
    "ny yankees": "new york yankees",
    "new york yankees": "new york yankees",
    "ny mets": "new york mets",
    "new york mets": "new york mets",
    "chi white sox": "chicago white sox",
    "chicago white sox": "chicago white sox",
    "chi cubs": "chicago cubs",
    "chicago cubs": "chicago cubs",
    "kc royals": "kansas city royals",
    "kansas city royals": "kansas city royals",
    "tb rays": "tampa bay rays",
    "tampa bay rays": "tampa bay rays",
    "sd padres": "san diego padres",
    "san diego padres": "san diego padres",
    "az diamondbacks": "arizona diamondbacks",
    "ari diamondbacks": "arizona diamondbacks",
    "arizona diamondbacks": "arizona diamondbacks",
}

def today_event_window():
    local_tz = ZoneInfo(MARKET_TIMEZONE)
    local_today = datetime.now(local_tz).date()

    local_start = datetime.combine(
        local_today,
        time.min,
        tzinfo=local_tz,
    )

    local_end = local_start + timedelta(days=1)

    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)

    return (
        utc_start.isoformat().replace("+00:00", "Z"),
        utc_end.isoformat().replace("+00:00", "Z"),
    )

def normalize(value: Any) -> str:
    return str(value or "").strip().lower()


def team_key(name: Any) -> str:
    key = normalize(name)
    key = key.replace(".", "")
    key = key.replace("&", "and")
    key = " ".join(key.split())

    if key.startswith("the "):
        key = key[4:]

    return TEAM_ALIASES.get(key, key)


def game_key(away_team: Any, home_team: Any) -> str:
    return f"{team_key(away_team)}@{team_key(home_team)}"


def to_float(value: Any, default=None):
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def decimal_to_american(value: Any):
    decimal = to_float(value)

    if decimal is None or decimal <= 1:
        return None

    if decimal >= 2:
        return round((decimal - 1) * 100)

    return round(-100 / (decimal - 1))


def get_json(path: str, params: dict[str, Any]):
    if not API_KEY:
        raise RuntimeError(
            "ODDS_API_IO_KEY is missing from .env. "
            "Add ODDS_API_IO_KEY=your_key and reopen the terminal."
        )

    query = dict(params)
    query["apiKey"] = API_KEY

    response = requests.get(
        f"{BASE_URL}/{path.lstrip('/')}",
        params=query,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 401:
        raise RuntimeError("Odds-API.io unauthorized. Check ODDS_API_IO_KEY.")
    if response.status_code in (402, 403):
        raise RuntimeError(
            "Odds-API.io rejected this request. Check your plan and bookmaker access."
        )
    if response.status_code == 429:
        raise RuntimeError("Odds-API.io rate limit exceeded.")

    if response.status_code >= 400:
        print("⚠️ Odds-API.io request failed")
        print("URL:", response.url)
        print("Status:", response.status_code)
        print("Body:", response.text[:1200])

    response.raise_for_status()
    return response.json()


def safe_load_json(path: Path, default):
    if not path.exists():
        return default

    try:
        return load_json(path, default=default)
    except Exception as exc:
        print(f"⚠️ Could not read {path}: {exc}")
        return default


def local_slate_window():
    tz = ZoneInfo(MARKET_TIMEZONE)
    local_now = datetime.now(tz)
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_end = local_start + timedelta(days=1)

    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)

    return (
        utc_start.isoformat().replace("+00:00", "Z"),
        utc_end.isoformat().replace("+00:00", "Z"),
    )


def fetch_today_events():
    start, end = today_event_window()

    payload = get_json(
        "events",
        {
            "sport": "baseball",
            "league": "usa-mlb",
            "status": "pending",
            "from": start,
            "to": end,
        },
    )

    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("events", "data", "results", "items"):
            value = payload.get(key)

            if isinstance(value, list):
                return value

    return []


def fetch_event_odds(event_id):
    if not event_id:
        return {}

    payload = get_json(
        "odds",
        {
            "eventId": event_id,
            "bookmakers": ",".join(BOOKMAKERS),
        },
    )

    return payload if isinstance(payload, dict) else {}


def find_matching_game(api_event, local_games, used_game_ids):
    api_away = team_key(api_event.get("away"))
    api_home = team_key(api_event.get("home"))

    candidates = []

    for game in local_games:
        game_id = str(game.get("game_id") or "")
        if game_id in used_game_ids:
            continue

        local_away = team_key(game.get("away_team"))
        local_home = team_key(game.get("home_team"))

        if local_away == api_away and local_home == api_home:
            candidates.append(game)

    if candidates:
        return candidates[0]

    return None


def get_book_markets(odds_payload, bookmaker):
    bookmakers = odds_payload.get("bookmakers", {})

    if not isinstance(bookmakers, dict):
        return []

    markets = bookmakers.get(bookmaker, [])
    return markets if isinstance(markets, list) else []


def find_market(markets, exact_name):
    target = normalize(exact_name)

    for market in markets:
        if normalize(market.get("name")) == target:
            return market

    return None


def first_odds_row(market):
    if not market:
        return {}

    odds = market.get("odds", [])
    if isinstance(odds, list) and odds:
        return odds[0]

    return {}


def first_available_market(odds_payload, market_name):
    for bookmaker in BOOKMAKERS:
        market = find_market(get_book_markets(odds_payload, bookmaker), market_name)
        if market:
            return bookmaker, market

    return "", None


def parse_moneyline(odds_payload):
    bookmaker, market = first_available_market(odds_payload, "ML")
    row = first_odds_row(market)

    return {
        "bookmaker": bookmaker,
        "away": decimal_to_american(row.get("away")),
        "home": decimal_to_american(row.get("home")),
    }


def parse_spread(odds_payload):
    bookmaker, market = first_available_market(odds_payload, "Spread")
    row = first_odds_row(market)

    hdp = to_float(row.get("hdp"))

    return {
        "bookmaker": bookmaker,
        "away": -hdp if hdp is not None else None,
        "away_price": decimal_to_american(row.get("away")),
        "home": hdp,
        "home_price": decimal_to_american(row.get("home")),
    }


def parse_game_total(odds_payload):
    bookmaker, market = first_available_market(odds_payload, "Totals")
    row = first_odds_row(market)

    return {
        "bookmaker": bookmaker,
        "line": to_float(row.get("hdp")),
        "over_price": decimal_to_american(row.get("over")),
        "under_price": decimal_to_american(row.get("under")),
    }


def parse_team_totals(odds_payload):
    result = {
        "away": None,
        "away_over_price": None,
        "away_under_price": None,
        "home": None,
        "home_over_price": None,
        "home_under_price": None,
    }

    for bookmaker in BOOKMAKERS:
        markets = get_book_markets(odds_payload, bookmaker)
        away_market = find_market(markets, "Team Total (Runs) Away")
        home_market = find_market(markets, "Team Total (Runs) Home")

        if away_market:
            row = first_odds_row(away_market)
            result["away"] = to_float(row.get("hdp"))
            result["away_over_price"] = decimal_to_american(row.get("over"))
            result["away_under_price"] = decimal_to_american(row.get("under"))

        if home_market:
            row = first_odds_row(home_market)
            result["home"] = to_float(row.get("hdp"))
            result["home_over_price"] = decimal_to_american(row.get("over"))
            result["home_under_price"] = decimal_to_american(row.get("under"))

        if away_market or home_market:
            break

    return result


def extract_player_from_prop_label(label):
    suffix = "(Pitcher Strikeouts)"
    value = str(label or "").strip()

    if not value.endswith(suffix):
        return ""

    return value[: -len(suffix)].strip()


def parse_pitcher_strikeouts(odds_payload):
    props = {}

    for bookmaker in BOOKMAKERS:
        markets = get_book_markets(odds_payload, bookmaker)
        player_props = find_market(markets, "Player Props")

        if not player_props:
            continue

        rows = player_props.get("odds", [])
        if not isinstance(rows, list):
            continue

        for row in rows:
            player = extract_player_from_prop_label(row.get("label"))
            line = to_float(row.get("hdp"))

            if not player or line is None:
                continue

            normalized_name = normalize_player_name(player)
            if not normalized_name or normalized_name in props:
                continue

            props[normalized_name] = {
                "player": player,
                "normalized_name": normalized_name,
                "line": line,
                "over_price": decimal_to_american(row.get("over")),
                "under_price": decimal_to_american(row.get("under")),
                "bookmaker": bookmaker,
                "bookmaker_key": bookmaker.lower().replace(" ", ""),
                "market_name": "Pitcher Strikeouts",
            }

    return props


def build_live_payload(api_event, local_game, odds_payload):
    moneyline = parse_moneyline(odds_payload)
    spread = parse_spread(odds_payload)
    game_total = parse_game_total(odds_payload)
    team_totals = parse_team_totals(odds_payload)
    pitcher_props = parse_pitcher_strikeouts(odds_payload)

    main_bookmaker = (
        moneyline.get("bookmaker")
        or spread.get("bookmaker")
        or game_total.get("bookmaker")
        or ""
    )

    return {
        "game_id": local_game.get("game_id"),
        "game": local_game.get("game"),
        "away_team": local_game.get("away_team"),
        "home_team": local_game.get("home_team"),
        "bookmaker": main_bookmaker,
        "bookmaker_key": main_bookmaker.lower().replace(" ", ""),
        "odds_event_id": api_event.get("id"),
        "moneyline": {
            "away": moneyline.get("away"),
            "home": moneyline.get("home"),
        },
        "spread": {
            "away": spread.get("away"),
            "away_price": spread.get("away_price"),
            "home": spread.get("home"),
            "home_price": spread.get("home_price"),
        },
        "total": game_total.get("line"),
        "game_total": {
            "line": game_total.get("line"),
            "over_price": game_total.get("over_price"),
            "under_price": game_total.get("under_price"),
        },
        "team_totals": team_totals,
        "pitcher_strikeouts": pitcher_props,
        "market_source": "odds_api_io",
        "market_status": "live",
        "market_updated_at": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }


def unavailable_payload(game, reason):
    return {
        "game_id": game.get("game_id"),
        "game": game.get("game"),
        "away_team": game.get("away_team"),
        "home_team": game.get("home_team"),
        "bookmaker": "",
        "bookmaker_key": "",
        "odds_event_id": "",
        "moneyline": {"away": None, "home": None},
        "spread": {
            "away": None,
            "away_price": None,
            "home": None,
            "home_price": None,
        },
        "total": None,
        "game_total": {
            "line": None,
            "over_price": None,
            "under_price": None,
        },
        "team_totals": {
            "away": None,
            "away_over_price": None,
            "away_under_price": None,
            "home": None,
            "home_over_price": None,
            "home_under_price": None,
        },
        "pitcher_strikeouts": {},
        "market_source": "unavailable",
        "market_status": reason,
    }


def has_usable_market_data(payload):
    if not isinstance(payload, dict):
        return False

    if payload.get("market_source") == "unavailable":
        return False

    moneyline = payload.get("moneyline", {}) or {}
    game_total = payload.get("game_total", {}) or {}
    pitcher_props = payload.get("pitcher_strikeouts", {}) or {}

    return bool(
        moneyline.get("away") is not None
        or moneyline.get("home") is not None
        or game_total.get("line") is not None
        or pitcher_props
    )


def load_cache_lookup():
    rows = safe_load_json(CACHE_FILE, [])

    if not rows:
        rows = safe_load_json(OUTPUT_FILE, [])

    lookup = {}

    if not isinstance(rows, list):
        return lookup

    for row in rows:
        if not has_usable_market_data(row):
            continue

        key = game_key(row.get("away_team"), row.get("home_team"))
        lookup.setdefault(key, []).append(row)

    return lookup


def cached_payload(game, cache_lookup):
    key = game_key(game.get("away_team"), game.get("home_team"))
    candidates = cache_lookup.get(key, [])

    if not candidates:
        return None

    cached = candidates.pop(0)
    payload = dict(cached)
    payload["game_id"] = game.get("game_id")
    payload["game"] = game.get("game")
    payload["away_team"] = game.get("away_team")
    payload["home_team"] = game.get("home_team")
    payload["market_status"] = "cached"

    return payload


def save_cache(output):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    save_json(output, CACHE_FILE)

    today = datetime.now(ZoneInfo(MARKET_TIMEZONE)).strftime("%Y-%m-%d")
    save_json(output, CACHE_DIR / f"market_lines_{today}.json")


def build_market_lines():
    local_games = safe_load_json(ALL_GAMES_FILE, [])

    if not isinstance(local_games, list):
        raise RuntimeError(f"{ALL_GAMES_FILE} must contain a JSON list.")

    cache = load_cache_lookup()
    output_by_game_id = {}
    used_game_ids = set()
    api_failed = False

    try:
        api_events = fetch_today_events()
        print(f"📅 Odds-API.io returned {len(api_events)} pending MLB events today")

        for api_event in api_events:
            local_game = find_matching_game(api_event, local_games, used_game_ids)

            if not local_game:
                print(
                    "⚠️ Could not match odds event: "
                    f"{api_event.get('away')} @ {api_event.get('home')}"
                )
                continue

            odds_payload = fetch_event_odds(api_event.get("id"))
            payload = build_live_payload(api_event, local_game, odds_payload)

            game_id = str(local_game.get("game_id"))
            output_by_game_id[game_id] = payload
            used_game_ids.add(game_id)

            print(
                f"   {local_game.get('game')}: "
                f"{len(payload['pitcher_strikeouts'])} pitcher K props"
            )

    except Exception as exc:
        api_failed = True
        print(f"⚠️ Odds-API.io failed: {exc}")

    for game in local_games:
        game_id = str(game.get("game_id"))

        if game_id in output_by_game_id:
            continue

        cached = cached_payload(game, cache)

        if cached:
            output_by_game_id[game_id] = cached
        else:
            reason = "api_unavailable" if api_failed else "not_returned_by_provider"
            output_by_game_id[game_id] = unavailable_payload(game, reason)

    output = list(output_by_game_id.values())

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, OUTPUT_FILE)
    save_cache(output)

    live_count = sum(
        1 for item in output if item.get("market_status") == "live"
    )
    cached_count = sum(
        1 for item in output if item.get("market_status") == "cached"
    )
    prop_count = sum(
        len(item.get("pitcher_strikeouts", {})) for item in output
    )

    print(f"✅ Saved market lines for {len(output)} games")
    print(f"   Live: {live_count} | Cached: {cached_count}")
    print(f"   Pitcher K props: {prop_count}")
    print(f"📁 {OUTPUT_FILE}")

    return output


if __name__ == "__main__":
    build_market_lines()
