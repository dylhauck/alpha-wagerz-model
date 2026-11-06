"""Fetch NFL quarter/half markets separately from full-game market.json."""
from __future__ import annotations
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from providers.nba.nba_live_markets import api_get, parse_team, merge_market, norm
from providers.odds_bulk import fetch_many
from providers.nfl.nfl_odds import normalize_team

ROOT=Path(__file__).resolve().parents[2]
load_dotenv(ROOT/".env")
MODEL=ROOT/"data"/"processed"/"nfl"
WEB=ROOT.parent/"alpha-wagerz-web"/"public"/"data"/"nfl"

def build_nfl_period_markets():
    key=os.getenv("ODDS_API_IO_KEY")
    if not key:
        print("NFL period markets: missing ODDS_API_IO_KEY; preserving existing files",flush=True)
        return
    books=[x.strip() for x in os.getenv("NFL_ODDS_API_IO_BOOKMAKERS","FanDuel,DraftKings").split(",") if x.strip()]
    now=datetime.now(timezone.utc)
    try:
        events=api_get("events",{"apiKey":key,"sport":"american-football",
            "league":os.getenv("NFL_ODDS_API_IO_LEAGUE","usa-nfl"),
            "status":"pending","from":(now-timedelta(hours=3)).isoformat(),
            "to":(now+timedelta(days=8)).isoformat()})
        if isinstance(events,dict): events=events.get("events",[])
        if not isinstance(events,list): raise ValueError("Invalid events response")
    except Exception as exc:
        print(f"NFL period markets event fetch failed: {exc}",flush=True)
        return
    for subdir in ("","next"):
        slate_path=MODEL/subdir/"slate.json"
        if not slate_path.exists(): continue
        slate=json.loads(slate_path.read_text(encoding="utf-8"))
        games=slate if isinstance(slate,list) else slate.get("games",[])
        lookup={(normalize_team(g.get("away_team") or g.get("away")),
                 normalize_team(g.get("home_team") or g.get("home"))):g
                for g in games if isinstance(g,dict)}
        targets=[]
        for e in events:
            if not isinstance(e,dict): continue
            away=normalize_team(e.get("away"))
            home=normalize_team(e.get("home"))
            game=lookup.get((away,home))
            eid=e.get("id") or e.get("eventId")
            if game is not None and eid: targets.append((eid,game,away,home))
        if not targets:
            print(f"NFL {subdir or 'current'}: no matching pending events",flush=True)
            continue
        def single(eid):
            return api_get("odds",{"apiKey":key,"eventId":eid,"bookmakers":",".join(books)})
        def multi(ids):
            return api_get("odds/multi",{"apiKey":key,"eventIds":",".join(ids),"bookmakers":",".join(books)})
        try:
            fetched=fetch_many([x[0] for x in targets],single,multi,workers=3)
        except Exception as exc:
            print(f"NFL period odds fetch failed: {exc}",flush=True)
            continue
        output=[]
        for eid,g,away,home in targets:
            raw=fetched.get(str(eid))
            if not isinstance(raw,dict): continue
            if "bookmakers" not in raw and isinstance(raw.get("data"),dict):raw=raw["data"]
            bookmakers=raw.get("bookmakers",{})
            if isinstance(bookmakers,dict):
                items=[(name,markets) for name,markets in bookmakers.items() if isinstance(markets,list)]
            elif isinstance(bookmakers,list):
                items=[(b.get("name") or b.get("title"),b.get("markets",[])) for b in bookmakers if isinstance(b,dict)]
            else:items=[]
            periods={}
            for book in books:
                entry=next(((n,m) for n,m in items if norm(n)==norm(book)),None)
                if not entry:continue
                _,parsed=parse_team(*entry)
                for label,market in parsed.items():
                    periods[label]=merge_market(periods.get(label),market)
            if periods:
                output.append({"game_id":g.get("game_id"),"away_team":away,
                    "home_team":home,"periods":periods})
            else:
                print(f"NFL {away} @ {home}: provider returned no recognized period markets",flush=True)
        if not output:
            print(f"NFL {subdir or 'current'}: no parsed period markets; preserving previous file",flush=True)
            continue
        payload={"generated_at":now.isoformat(),"games":output}
        for directory in (MODEL/subdir,WEB/subdir):
            directory.mkdir(parents=True,exist_ok=True)
            (directory/"period_markets.json").write_text(json.dumps(payload,indent=2),encoding="utf-8")
        print(f"NFL {subdir or 'current'}: saved period markets for {len(output)} games",flush=True)

if __name__=="__main__":
    build_nfl_period_markets()
