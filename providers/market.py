import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from utils.json_utils import load_json, save_json

load_dotenv(dotenv_path=Path.cwd() / ".env")

API_KEY = os.getenv("THE_ODDS_API_KEY")

ALL_GAMES_FILE = Path("data/processed/all_games.json")
OUTPUT_FILE = Path("data/processed/market_lines.json")

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
}


def normalize(value):
    return str(value or "").strip().lower()


def team_key(name):
    key = normalize(name).replace(".", "").replace("the ", "")
    return TEAM_ALIASES.get(key, key)


def get_json(url, params):
    if not API_KEY:
        raise ValueError("THE_ODDS_API_KEY missing from .env")

    params = dict(params)
    params["apiKey"] = API_KEY

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def market_count(book):
    wanted = {"h2h", "spreads", "totals", "team_totals", "pitcher_strikeouts"}
    keys = {market.get("key") for market in book.get("markets", [])}
    return len(keys.intersection(wanted))


def pick_bookmaker(bookmakers):
    if not bookmakers:
        return None

    ranked = sorted(
        bookmakers,
        key=lambda book: (
            market_count(book),
            -BOOK_PRIORITY.index(book.get("key"))
            if book.get("key") in BOOK_PRIORITY
            else -999,
        ),
        reverse=True,
    )

    return ranked[0]


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

        # Safety fallback in case an odds provider ever flips display order.
        if local_away == api_home and local_home == api_away:
            return game

    return None


def fetch_main_markets():
    now = datetime.now(timezone.utc)
    commence_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
    commence_to = commence_from + timedelta(days=1)

    return get_json(
        f"{BASE_URL}/odds",
        {
            "regions": "us",
            "markets": "h2h,spreads,totals",
            "oddsFormat": "american",
            "commenceTimeFrom": commence_from.isoformat().replace("+00:00", "Z"),
            "commenceTimeTo": commence_to.isoformat().replace("+00:00", "Z"),
        },
    )


def fetch_event_props(event_id):
    try:
        return get_json(
            f"{BASE_URL}/events/{event_id}/odds",
            {
                "regions": "us",
                "markets": "team_totals,pitcher_strikeouts",
                "oddsFormat": "american",
            },
        )
    except Exception as e:
        print(f"⚠️ Props unavailable for event {event_id}: {e}")
        return {}


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

    book = pick_bookmaker(event_props.get("bookmakers", []))

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


def parse_pitcher_strikeouts(event_props):
    props = {}

    book = pick_bookmaker(event_props.get("bookmakers", []))
    if not book:
        return props

    market = market_by_key(book, "pitcher_strikeouts")
    if not market:
        return props

    for outcome in market.get("outcomes", []):
        player = outcome.get("description") or outcome.get("name")
        side = outcome.get("name")
        point = outcome.get("point")
        price = outcome.get("price")

        if not player or point is None:
            continue

        if player not in props:
            props[player] = {
                "line": point,
                "over_price": None,
                "under_price": None,
            }

        props[player]["line"] = point

        if side == "Over":
            props[player]["over_price"] = price
        elif side == "Under":
            props[player]["under_price"] = price

    return props


def build_market_lines():
    local_games = load_json(ALL_GAMES_FILE, default=[])
    api_games = fetch_main_markets()

    output = []

    for api_game in api_games:
        local_game = find_matching_game(api_game, local_games)

        if not local_game:
            print(
                "⚠️ Could not match odds game: "
                f"{api_game.get('away_team')} @ {api_game.get('home_team')}"
            )
            continue

        book = pick_bookmaker(api_game.get("bookmakers", []))
        if not book:
            print(f"⚠️ No bookmaker found for {local_game.get('game')}")
            continue

        away_team = local_game.get("away_team")
        home_team = local_game.get("home_team")

        h2h = market_by_key(book, "h2h")
        spreads = market_by_key(book, "spreads")
        totals = market_by_key(book, "totals")
        team_totals_market = market_by_key(book, "team_totals")

        away_ml = outcome_for_team(h2h, away_team)
        home_ml = outcome_for_team(h2h, home_team)

        away_spread = outcome_for_team(spreads, away_team)
        home_spread = outcome_for_team(spreads, home_team)

        game_total = parse_game_total(totals)
        
        event_props = fetch_event_props(api_game.get("id"))
        pitcher_props = parse_pitcher_strikeouts(event_props)
        team_totals = parse_team_totals(event_props, away_team, home_team)

        output.append(
            {
                "game_id": local_game.get("game_id"),
                "game": local_game.get("game"),
                "away_team": away_team,
                "home_team": home_team,
                "bookmaker": book.get("title"),
                "bookmaker_key": book.get("key"),
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
                # Keep both formats so older projection code still works.
                "total": game_total.get("line"),
                "game_total": game_total,
                "team_totals": team_totals,
                "pitcher_strikeouts": pitcher_props,
            }
        )

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    save_json(output, OUTPUT_FILE)

    print(f"✅ Saved market lines for {len(output)} games")
    print(f"📁 {OUTPUT_FILE}")

    return output


if __name__ == "__main__":
    build_market_lines()
