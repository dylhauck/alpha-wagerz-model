"""Fetch verified NHL sportsbook lines for current and next slate.

Odds-API.io is the market source; Alpha projections are computed separately.
Never fabricate a missing market or overwrite a populated market file with an empty response.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from providers.nba.nba_live_markets import api_get, bookmaker_items, parse_team, merge_market, norm
from providers.odds_bulk import fetch_many

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DATA = ROOT / "data" / "processed" / "nhl"
WEB = ROOT.parent / "alpha-wagerz-web" / "public" / "data" / "nhl"
NAMES = {
"ANA":"Anaheim Ducks","BOS":"Boston Bruins","BUF":"Buffalo Sabres",
"CAR":"Carolina Hurricanes","CBJ":"Columbus Blue Jackets","CGY":"Calgary Flames",
"CHI":"Chicago Blackhawks","COL":"Colorado Avalanche","DAL":"Dallas Stars",
"DET":"Detroit Red Wings","EDM":"Edmonton Oilers","FLA":"Florida Panthers",
"LAK":"Los Angeles Kings","MIN":"Minnesota Wild","MTL":"Montreal Canadiens",
"NJD":"New Jersey Devils","NSH":"Nashville Predators","NYI":"New York Islanders",
"NYR":"New York Rangers","OTT":"Ottawa Senators","PHI":"Philadelphia Flyers",
"PIT":"Pittsburgh Penguins","SEA":"Seattle Kraken","SJS":"San Jose Sharks",
"STL":"St. Louis Blues","TBL":"Tampa Bay Lightning","TOR":"Toronto Maple Leafs",
"UTA":"Utah Mammoth","VAN":"Vancouver Canucks","VGK":"Vegas Golden Knights",
"WPG":"Winnipeg Jets","WSH":"Washington Capitals",
}
ALIASES = {norm(name): abbr for abbr, name in NAMES.items()}
ALIASES.update({norm(abbr): abbr for abbr in NAMES})
ALIASES.update({"utahhockeyclub":"UTA","utahhockey":"UTA","utahmammoth":"UTA",
"losangeleskings":"LAK","lakings":"LAK","columbusbluejackets":"CBJ",
"montrealcanadiens":"MTL","tampabaylightning":"TBL","sanjosesharks":"SJS"})

def team(value):
    if isinstance(value, dict):
        value = value.get("name") or value.get("team") or value.get("abbreviation")
    return ALIASES.get(norm(value))

def event_teams(event):
    return team(event.get("away") or event.get("awayTeam") or event.get("away_team")), team(event.get("home") or event.get("homeTeam") or event.get("home_team"))

def get_events(key, league):
    now = datetime.now(timezone.utc)
    result = api_get("events", {"apiKey": key, "sport": "ice-hockey", "league": league,
        "status": "pending", "from": (now-timedelta(hours=3)).isoformat(),
        "to": (now+timedelta(days=3)).isoformat()})
    return result.get("events", []) if isinstance(result, dict) else result

def hockey_markets(markets):
    """Normalize NHL period labels and market types without changing prices."""
    converted=[]
    for market in markets:
        if not isinstance(market,dict): continue
        row=dict(market)
        name=str(row.get("name") or row.get("market") or row.get("type") or row.get("key") or "")
        period=None
        for expression,label in ((r"\b(?:1st|first)\s+period\b|\bperiod\s*1\b|\bp1\b|\b1p\b","Q1"),
                                 (r"\b(?:2nd|second)\s+period\b|\bperiod\s*2\b|\bp2\b|\b2p\b","Q2"),
                                 (r"\b(?:3rd|third)\s+period\b|\bperiod\s*3\b|\bp3\b|\b3p\b","Q3")):
            if re.search(expression,name,re.IGNORECASE):
                period=label
                name=re.sub(expression," ",name,flags=re.IGNORECASE)
                break
        if not period:
            converted.append(row)
            continue
        normalized=name.strip().lower()
        if any(x in normalized for x in ("3-way","3 way","three way","draw","1x2")): continue
        if any(x in normalized for x in ("moneyline","money line","winner","to win","result")): kind="Moneyline"
        elif any(x in normalized for x in ("puck line","puckline","spread","handicap")): kind="Spread"
        elif any(x in normalized for x in ("team total","team goals")): kind="Team Total"
        elif any(x in normalized for x in ("total","over/under","over under","goals")): kind="Total"
        else: continue
        row["name"]=period+" "+kind+(" "+normalized if kind=="Team Total" else "")
        if not isinstance(row.get("odds"),list):
            selections=row.get("outcomes") or row.get("selections")
            if isinstance(selections,list): row["odds"]=selections
        converted.append(row)
    return converted

def build_nhl_live_markets():
    key = os.getenv("ODDS_API_IO_KEY")
    if not key:
        print("NHL sportsbook markets: ODDS_API_IO_KEY missing; retaining previous files", flush=True)
        return
    books = [b.strip() for b in os.getenv("NHL_ODDS_BOOKMAKERS", "FanDuel,DraftKings").split(",") if b.strip()]
    # Provider's canonical NHL league is usa-nhl. Do not silently substitute another league.
    try:
        events = get_events(key, os.getenv("NHL_ODDS_LEAGUE", "usa-nhl"))
        if not isinstance(events, list):
            raise ValueError("Invalid NHL event response")
    except Exception as exc:
        print(f"NHL sportsbook events unavailable: {exc}", flush=True)
        return
    for subdir in ("", "next"):
        slate_file = DATA / subdir / "slate.json"
        if not slate_file.exists():
            print(f"NHL sportsbook slate missing: {slate_file}", flush=True)
            continue
        slate = json.loads(slate_file.read_text(encoding="utf-8"))
        games = slate.get("games", [])
        matched = {(g["away"],g["home"]):g for g in games}
        targets = []
        for event in events:
            if not isinstance(event,dict):
                continue
            away,home = event_teams(event)
            eid = event.get("id") or event.get("eventId")
            if eid and (away,home) in matched:
                targets.append((eid,matched[(away,home)]))
        if not targets:
            print(f"NHL {subdir or 'current'}: no matching pending sportsbook events; retaining existing file", flush=True)
            continue
        def single(event_id):
            return api_get("odds", {"apiKey":key,"eventId":event_id,"bookmakers":",".join(books)})
        def multi(event_ids):
            return api_get("odds/multi", {"apiKey":key,"eventIds":",".join(event_ids),"bookmakers":",".join(books)})
        try:
            odds = fetch_many([eid for eid,_ in targets],single,multi,workers=3)
        except Exception as exc:
            print(f"NHL odds fetch failed: {exc}",flush=True)
            continue
        output = []
        for eid, game in targets:
            raw = odds.get(str(eid))
            if not isinstance(raw,dict):
                continue
            if "bookmakers" not in raw and isinstance(raw.get("data"),dict):
                raw=raw["data"]
            # Do not use the NBA helper: it filters using NBA bookmaker settings.
            bookmakers=raw.get("bookmakers",{})
            if isinstance(bookmakers,dict):
                entries=[(name,markets) for name,markets in bookmakers.items() if isinstance(markets,list)]
            elif isinstance(bookmakers,list):
                entries=[(str(b.get("name") or b.get("title")),b.get("markets",[])) for b in bookmakers if isinstance(b,dict) and isinstance(b.get("markets"),list)]
            else:
                entries=[]
            full={}
            periods={}
            for book in books:
                found=next(((name, markets) for name,markets in entries if norm(name)==norm(book)),None)
                if found:
                    converted=hockey_markets(found[1])
                    parsed,partial=parse_team(found[0],converted)
                    recognized=[m.get("name") for m in converted if isinstance(m,dict) and re.match(r"^Q[123] ",str(m.get("name","")))]
                    print(f"NHL period markets {game['away']} @ {game['home']} {book}: {len(recognized)} recognized, parsed {list(partial)}",flush=True)
                    full=merge_market(full,parsed)
                    for label,market in partial.items():
                        label={"Q1":"1st Period","Q2":"2nd Period","Q3":"3rd Period"}.get(label,label)
                        periods[label]=merge_market(periods.get(label),market)
            if any(full.get(k) for k in ("moneyline","spread","total","team_totals")) or any(any(m.get(k) for k in ("moneyline","spread","total","team_totals")) for m in periods.values()):
                print(f"NHL {game['away']} @ {game['home']}: parsed periods {list(periods)}",flush=True)
                output.append({"game_id":game["game_id"],"away_team":game["away"],"home_team":game["home"],
                    "event_id":eid,"full_game":full,"periods":periods})
        if not output:
            print(f"NHL {subdir or 'current'}: provider returned no recognized markets; retaining existing file",flush=True)
            continue
        payload={"generated_at":datetime.now(timezone.utc).isoformat(),"games":output}
        for folder in (DATA / subdir,WEB / subdir):
            folder.mkdir(parents=True,exist_ok=True)
            (folder/"live_team_markets.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
        print(f"NHL {subdir or 'current'} sportsbook markets: {len(output)} games matched",flush=True)

if __name__=="__main__":
    build_nhl_live_markets()
