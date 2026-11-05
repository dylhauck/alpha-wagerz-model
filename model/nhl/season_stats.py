"""Official NHL club-stat season datasets and standings.

Uses NHL public endpoints; validates completeness before publishing so a provider
failure never replaces usable data with an empty table.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
from .build_nhl import fetch,save

def _name(value):
    return value.get("default","") if isinstance(value,dict) else str(value or "")

def _season_id():
    now=datetime.now(ZoneInfo("America/Chicago"))
    start=now.year if now.month>=9 else now.year-1
    return f"{start}{start+1}"

def _team_codes(standings):
    return sorted({(r.get("teamAbbrev") or {}).get("default","") for r in standings if (r.get("teamAbbrev") or {}).get("default")})

def _load_club(code,season):
    return code,fetch(f"club-stats/{code}/{season}/2")

def _rows(results):
    skaters=[];goalies=[]
    for code,payload in results.items():
        for p in payload.get("skaters") or []:
            games=int(p.get("gamesPlayed") or 0)
            if not games:continue
            goals=int(p.get("goals") or 0);shots=int(p.get("shots") or 0)
            skaters.append({"player_id":str(p.get("playerId") or ""),"name":(_name(p.get("firstName"))+" "+_name(p.get("lastName"))).strip(),"team":code,"position":p.get("positionCode") or "","games":games,"goals":goals,"assists":int(p.get("assists") or 0),"points":int(p.get("points") or 0),"shots":shots,"goals_per_game":round(goals/games,3),"shots_per_game":round(shots/games,3)})
        for p in payload.get("goalies") or []:
            games=int(p.get("gamesPlayed") or 0)
            if not games:continue
            saves=int(p.get("saves") or 0);shots=int(p.get("shotsAgainst") or 0)
            against=int(p.get("goalsAgainst") or 0)
            goalies.append({"player_id":str(p.get("playerId") or ""),"name":(_name(p.get("firstName"))+" "+_name(p.get("lastName"))).strip(),"team":code,"position":"G","games":games,"saves":saves,"shots_against":shots,"goals_against":against,"save_percentage":round(saves/shots,3) if shots else None,"goals_against_per_appearance":round(against/games,2)})
    return {"players":skaters,"goalies":goalies}

def build_nhl_season_stats():
    standings=fetch("standings/now").get("standings") or []
    codes=_team_codes(standings)
    if len(codes)<30:raise ValueError(f"Only {len(codes)} NHL teams in standings response")
    current=_season_id()
    previous=f"{int(current[:4])-1}{int(current[4:])-1}"
    for season,filename in ((current,"players.json"),(previous,"players_last_season.json")):
        results={}
        with ThreadPoolExecutor(max_workers=12) as pool:
            futures={pool.submit(_load_club,code,season):code for code in codes}
            for future in as_completed(futures):
                try:
                    code,payload=future.result()
                    if isinstance(payload,dict) and ("skaters" in payload or "goalies" in payload):results[code]=payload
                except Exception as exc:print(f"NHL club stats {futures[future]} {season}: {exc}",flush=True)
        dataset=_rows(results)
        if len(results)<30 or len(dataset["players"])<300:
            print(f"NHL {season}: incomplete ({len(results)} clubs, {len(dataset['players'])} skaters); retaining existing data",flush=True)
            continue
        save("",filename,dataset)
        print(f"NHL {season}: published {len(dataset['players'])} skaters, {len(dataset['goalies'])} goalies",flush=True)
    # Team standings are consumed by the website's live NHL standings route.
    save("","standings.json",{"season":current,"standings":standings})
