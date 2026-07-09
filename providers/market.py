import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from utils.json_utils import load_json, save_json
from utils.player_name import normalize_player_name

load_dotenv(dotenv_path=Path.cwd() / ".env")

API_KEY = os.getenv("THE_ODDS_API_KEY")

ALL_GAMES_FILE = Path("data/processed/all_games.json")
OUTPUT_FILE = Path("data/processed/market_lines.json")
CACHE_DIR = Path("data/cache/markets")
CACHE_FILE = CACHE_DIR / "latest_market_lines.json"

BASE_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb"

BOOK_PRIORITY = [
    "draftkings",
    "fanduel",
    "fanatics",
    "betmgm",
    "caesars",
    "espnbet",
    "bet365",
    "pointsbetus",
    "betrivers",
    "betonlineag",
]

TEAM_ALIASES = {
    "athletics": "oakland athletics",
    "oakland athletics": "oakland athletics",
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
    "chicago white sox": "chicago white sox",
    "chi white sox": "chicago white sox",
    "chicago cubs": "chicago cubs",
    "chi cubs": "chicago cubs",
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


def normalize(value):
    return str(value or "").strip().lower()


def team_key(name):
    key = normalize(name)
    key = key.replace(".", "")
    key = key.replace("&", "and")
    key = key.replace("the ", "")
    key = " ".join(key.split())
    return TEAM_ALIASES.get(key, key)


def game_key(away_team, home_team):
    return f"{team_key(away_team)}@{team_key(home_team)}"


def priority_rank(book_key):
    if book_key in BOOK_PRIORITY:
        return len(BOOK_PRIORITY) - BOOK_PRIORITY.index(book_key)
    return 0


def market_count(book):
    wanted = {"h2h", "spreads", "totals", "team_totals", "pitcher_strikeouts"}
    keys = {market.get("key") for market in book.get("markets", [])}
    return len(keys.intersection(wanted))


def pick_bookmaker(bookmakers, required_market_key=None):
    if not bookmakers:
        return None

    candidates = bookmakers

    if required_market_key:
        candidates = [
            book
            for book in bookmakers
            if any(market.get("key") == required_market_key for market in book.get("markets", []))
        ]

        if not candidates:
            return None

    return sorted(
        candidates,
        key=lambda book: (market_count(book), priority_rank(book.get("key"))),
        reverse=True,
    )[0]


def market_by_key(book, key):
    if not book:
        return None

    for market in book.get("markets", []):
        if market.get("key") == key:
            return market

    return None


def outcome_for_team(market, team):
    if not market:
        return {}

    target = team_key(team)

    for outcome in market.get("outcomes", []):
        if team_key(outcome.get("name")) == target:
            return outcome

    return {}


def find_matching_game(api_game, local_games):
    api_away = team_key(api_game.get("away_team"))
    api_home = team_key(api_game.get("home_team"))

    for game in local_games:
        local_away = team_key(game.get("away_team"))
        local_home = team_key(game.get("home_team"))

        if local_away == api_away and local_home == api_home:
            return game

        if local_away == api_home and local_home == api_away:
            return game

    return None


def slate_windows():
    now = datetime.now(timezone.utc)
    start_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start_mlb = now.replace(hour=8, minute=0, second=0, microsecond=0)

    return [
        (start_midnight, start_midnight + timedelta(hours=24)),
        (start_mlb, start_mlb + timedelta(hours=24)),
    ]


def dedupe_by_id(items):
    seen = {}

    for item in items:
        item_id = item.get("id")
        if item_id:
            seen[item_id] = item

    return list(seen.values())


def api_available():
    return bool(API_KEY)


def get_json(url, params):
    if not API_KEY:
        raise RuntimeError("THE_ODDS_API_KEY missing from .env")

    params = dict(params)
    params["apiKey"] = API_KEY

    response = requests.get(url, params=params, timeout=30)

    if response.status_code == 401:
        raise RuntimeError("Odds API unauthorized. Check THE_ODDS_API_KEY.")

    if response.status_code == 402:
        raise RuntimeError("Odds API quota exceeded or payment required.")

    if response.status_code == 429:
        raise RuntimeError("Odds API rate limit exceeded.")

    if response.status_code >= 400:
        print("⚠️ Odds API request failed")
        print("URL:", response.url)
        print("Status:", response.status_code)
        print("Body:", response.text[:800])

    response.raise_for_status()
    return response.json()


def safe_get_json(url, params, fallback):
    try:
        return get_json(url, params)
    except Exception as e:
        print(f"⚠️ Odds API request skipped/failed: {e}")
        return fallback


def fetch_main_markets_from_api():
    all_games = []

    for commence_from, commence_to in slate_windows():
        games = get_json(
            f"{BASE_URL}/odds",
            {
                "regions": "us,us2",
                "markets": "h2h,spreads,totals",
                "oddsFormat": "american",
                "commenceTimeFrom": commence_from.isoformat().replace("+00:00", "Z"),
                "commenceTimeTo": commence_to.isoformat().replace("+00:00", "Z"),
            },
        )

        all_games.extend(games)

    return dedupe_by_id(all_games)


def fetch_events_from_api():
    all_events = []

    for commence_from, commence_to in slate_windows():
        events = safe_get_json(
            f"{BASE_URL}/events",
            {
                "commenceTimeFrom": commence_from.isoformat().replace("+00:00", "Z"),
                "commenceTimeTo": commence_to.isoformat().replace("+00:00", "Z"),
            },
            [],
        )

        all_events.extend(events)

    return dedupe_by_id(all_events)


def fetch_event_main_markets_from_api(event_id):
    if not event_id:
        return {}

    return safe_get_json(
        f"{BASE_URL}/events/{event_id}/odds",
        {
            "regions": "us,us2",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
        },
        {},
    )


def fetch_event_props_from_api(event_id):
    if not event_id:
        return {}

    data = safe_get_json(
        f"{BASE_URL}/events/{event_id}/odds",
        {
            "regions": "us,us2",
            "markets": "team_totals,pitcher_strikeouts",
            "oddsFormat": "american",
        },
        {},
    )

    if data and data.get("bookmakers"):
        return data

    team_totals = safe_get_json(
        f"{BASE_URL}/events/{event_id}/odds",
        {
            "regions": "us,us2",
            "markets": "team_totals",
            "oddsFormat": "american",
        },
        {},
    )

    k_props = safe_get_json(
        f"{BASE_URL}/events/{event_id}/odds",
        {
            "regions": "us,us2",
            "markets": "pitcher_strikeouts",
            "oddsFormat": "american",
        },
        {},
    )

    return merge_event_prop_payloads(team_totals, k_props)


def merge_event_prop_payloads(*payloads):
    merged = {}

    for payload in payloads:
        if not payload:
            continue

        if not merged:
            merged = {
                "id": payload.get("id"),
                "sport_key": payload.get("sport_key"),
                "home_team": payload.get("home_team"),
                "away_team": payload.get("away_team"),
                "bookmakers": [],
            }

        by_book = {book.get("key"): book for book in merged.get("bookmakers", [])}

        for book in payload.get("bookmakers", []):
            key = book.get("key")
            if not key:
                continue

            if key not in by_book:
                by_book[key] = {
                    "key": key,
                    "title": book.get("title"),
                    "markets": [],
                }
                merged["bookmakers"].append(by_book[key])

            existing_market_keys = {m.get("key") for m in by_book[key].get("markets", [])}

            for market in book.get("markets", []):
                if market.get("key") not in existing_market_keys:
                    by_book[key]["markets"].append(market)
                    existing_market_keys.add(market.get("key"))

    return merged


def parse_game_total(totals_market):
    if not totals_market:
        return {"line": None, "over_price": None, "under_price": None}

    parsed = {"line": None, "over_price": None, "under_price": None}

    for outcome in totals_market.get("outcomes", []):
        name = outcome.get("name")
        point = outcome.get("point")
        price = outcome.get("price")

        if point is not None:
            parsed["line"] = point

        if name == "Over":
            parsed["over_price"] = price
        elif name == "Under":
            parsed["under_price"] = price

    return parsed


def parse_team_totals(event_props, away_team, home_team):
    result = {
        "away": None,
        "away_over_price": None,
        "away_under_price": None,
        "home": None,
        "home_over_price": None,
        "home_under_price": None,
    }

    if not event_props:
        return result

    book = pick_bookmaker(event_props.get("bookmakers", []), required_market_key="team_totals")
    market = market_by_key(book, "team_totals")

    if not market:
        return result

    for outcome in market.get("outcomes", []):
        team = outcome.get("description") or outcome.get("name")
        side = outcome.get("name")
        point = outcome.get("point")
        price = outcome.get("price")

        if team_key(team) == team_key(away_team):
            if side == "Over":
                result["away"] = point
                result["away_over_price"] = price
            elif side == "Under":
                result["away_under_price"] = price

        if team_key(team) == team_key(home_team):
            if side == "Over":
                result["home"] = point
                result["home_over_price"] = price
            elif side == "Under":
                result["home_under_price"] = price

    return result


def merge_pitcher_prop(props, player, side, point, price, book_key=None):
    if not player or point is None:
        return

    player_clean = str(player).strip()
    player_key = normalize_player_name(player_clean)

    if not player_key:
        return

    if player_key not in props:
        props[player_key] = {
            "player": player_clean,
            "line": point,
            "over_price": None,
            "under_price": None,
            "bookmaker_key": book_key,
            "normalized_name": player_key,
        }

    if props[player_key].get("line") is None:
        props[player_key]["line"] = point

    if side == "Over" and props[player_key].get("over_price") is None:
        props[player_key]["over_price"] = price
    elif side == "Under" and props[player_key].get("under_price") is None:
        props[player_key]["under_price"] = price


def parse_pitcher_strikeouts(event_props):
    props = {}

    if not event_props:
        return props

    bookmakers = event_props.get("bookmakers", []) or []

    for book in bookmakers:
        market = market_by_key(book, "pitcher_strikeouts")
        if not market:
            continue

        for outcome in market.get("outcomes", []):
            player = outcome.get("description") or outcome.get("player") or outcome.get("name")
            side = outcome.get("name")
            point = outcome.get("point")
            price = outcome.get("price")

            if not player or point is None:
                continue

            key = normalize_player_name(player)

            if key not in props:
                props[key] = {
                    "player": player,
                    "normalized_name": key,
                    "line": point,
                    "over_price": None,
                    "under_price": None,
                    "bookmaker": book.get("title"),
                    "bookmaker_key": book.get("key"),
                }

            props[key]["line"] = point

            if side == "Over":
                props[key]["over_price"] = price
            elif side == "Under":
                props[key]["under_price"] = price

    return props


def market_payload_from_api(api_game, local_game, event_props=None):
    event_props = event_props or {}

    book = pick_bookmaker(api_game.get("bookmakers", []))
    if not book:
        return None

    away_team = local_game.get("away_team")
    home_team = local_game.get("home_team")

    h2h = market_by_key(book, "h2h")
    spreads = market_by_key(book, "spreads")
    totals = market_by_key(book, "totals")

    away_ml = outcome_for_team(h2h, away_team)
    home_ml = outcome_for_team(h2h, home_team)

    away_spread = outcome_for_team(spreads, away_team)
    home_spread = outcome_for_team(spreads, home_team)

    game_total = parse_game_total(totals)

    pitcher_props = parse_pitcher_strikeouts(event_props)
    team_totals = parse_team_totals(event_props, away_team, home_team)

    return {
        "game_id": local_game.get("game_id"),
        "game": local_game.get("game"),
        "away_team": away_team,
        "home_team": home_team,
        "bookmaker": book.get("title"),
        "bookmaker_key": book.get("key"),
        "odds_event_id": api_game.get("id") or event_props.get("id"),
        "moneyline": {
            "away": away_ml.get("price"),
            "home": home_ml.get("price"),
        },
        "spread": {
            "away": away_spread.get("point"),
            "away_price": away_spread.get("price"),
            "home": home_spread.get("point"),
            "home_price": home_spread.get("price"),
        },
        "total": game_total.get("line"),
        "game_total": game_total,
        "team_totals": team_totals,
        "pitcher_strikeouts": pitcher_props,
        "market_source": "the_odds_api",
        "market_status": "live",
    }


def load_cache():
    if CACHE_FILE.exists():
        return load_json(CACHE_FILE, default=[])

    if OUTPUT_FILE.exists():
        return load_json(OUTPUT_FILE, default=[])

    return []


def cache_lookup():
    rows = load_cache()
    by_game = {}

    for row in rows:
        key = game_key(row.get("away_team"), row.get("home_team"))
        if key:
            by_game[key] = row

    return by_game


def cached_payload_for_game(game, cached_by_game):
    key = game_key(game.get("away_team"), game.get("home_team"))
    cached = cached_by_game.get(key)

    if not cached:
        return None

    payload = dict(cached)
    payload["game_id"] = game.get("game_id")
    payload["game"] = game.get("game")
    payload["away_team"] = game.get("away_team")
    payload["home_team"] = game.get("home_team")
    payload["market_source"] = cached.get("market_source", "cache")
    payload["market_status"] = "cached"

    return payload


def unavailable_payload_for_game(game, reason):
    return {
        "game_id": game.get("game_id"),
        "game": game.get("game"),
        "away_team": game.get("away_team"),
        "home_team": game.get("home_team"),
        "bookmaker": "",
        "bookmaker_key": "",
        "odds_event_id": "",
        "moneyline": {"away": None, "home": None},
        "spread": {"away": None, "away_price": None, "home": None, "home_price": None},
        "total": None,
        "game_total": {"line": None, "over_price": None, "under_price": None},
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


def save_cache(output):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    save_json(output, CACHE_FILE)

    today = datetime.now().strftime("%Y-%m-%d")
    save_json(output, CACHE_DIR / f"market_lines_{today}.json")


def build_market_lines():
    local_games = load_json(ALL_GAMES_FILE, default=[])
    cached_by_game = cache_lookup()

    output_by_game_id = {}

    api_failed = False
    api_games = []
    api_events = []

    if api_available():
        try:
            api_games = fetch_main_markets_from_api()
            api_events = fetch_events_from_api()
        except Exception as e:
            api_failed = True
            print(f"⚠️ Odds API unavailable. Using cache where possible. Reason: {e}")
    else:
        api_failed = True
        print("⚠️ No THE_ODDS_API_KEY found. Using cache where possible.")

    print(f"💰 Odds API returned {len(api_games)} main market games")
    print(f"📅 Odds API returned {len(api_events)} events")

    if not api_failed:
        for api_game in api_games:
            local_game = find_matching_game(api_game, local_games)

            if not local_game:
                continue

            event_props = fetch_event_props_from_api(api_game.get("id"))
            payload = market_payload_from_api(api_game, local_game, event_props)

            if payload:
                output_by_game_id[str(local_game.get("game_id"))] = payload

        for api_event in api_events:
            local_game = find_matching_game(api_event, local_games)

            if not local_game:
                continue

            game_id = str(local_game.get("game_id"))

            if game_id in output_by_game_id:
                continue

            event_main = fetch_event_main_markets_from_api(api_event.get("id"))
            event_props = fetch_event_props_from_api(api_event.get("id"))

            if not event_main or not event_main.get("bookmakers"):
                continue

            payload = market_payload_from_api(event_main, local_game, event_props)

            if payload:
                output_by_game_id[game_id] = payload

    for game in local_games:
        game_id = str(game.get("game_id"))

        if game_id in output_by_game_id:
            continue

        cached = cached_payload_for_game(game, cached_by_game)

        if cached:
            output_by_game_id[game_id] = cached
            continue

        reason = "api_quota_or_unavailable" if api_failed else "not_returned_by_provider"
        output_by_game_id[game_id] = unavailable_payload_for_game(game, reason)

    output = list(output_by_game_id.values())

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, OUTPUT_FILE)
    save_cache(output)

    live = sum(1 for item in output if item.get("market_status") == "live")
    cached = sum(1 for item in output if item.get("market_status") == "cached")
    unavailable = sum(1 for item in output if item.get("market_source") == "unavailable")

    print(f"✅ Saved market lines for {len(output)} games")
    print(f"   Live: {live} | Cached: {cached} | Unavailable: {unavailable}")
    print(f"📁 {OUTPUT_FILE}")

    return output


if __name__ == "__main__":
    build_market_lines()
