"""Additional NHL feeds with bounded calls and conservative publishing.

Injury status is only published from explicitly labeled provider records.
Career totals are cached incrementally; incomplete sets are not published.
Matchup history uses final games from club schedules, not inferred scores.
"""
from __future__ import annotations
import json
import os
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from .build_nhl import DATA, fetch, save

ESPN="https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"
HEADERS={"User-Agent":"AlphaWagerz/1.0"}

def _fetch_espn():
    response=requests.get(ESPN,headers=HEADERS,timeout=10)
    response.raise_for_status()
    return response.json()

def build_nhl_injuries():
    """Fail closed: never replace a verified injury feed with empty/unknown data."""
    payload=_fetch_espn()
    if not isinstance(payload,dict) or not isinstance(payload.get("injuries"),list):
        raise ValueError("ESPN NHL injury response missing injuries list")
    rows=[]
    for group in payload["injuries"]:
        team=group.get("team") or {}
        code=str(team.get("abbreviation") or "").upper()
        for item in group.get("injuries") or []:
            athlete=item.get("athlete") or {}
            status=item.get("status") or item.get("type") or {}
            if isinstance(status,dict):status=status.get("description") or status.get("name")
            name=athlete.get("displayName") or athlete.get("fullName")
            if not name or not status:continue
            rows.append({"player":name,"name":name,"team":code,"status":str(status),
                         "detail":item.get("details") or {},"source":"ESPN"})
    # A zero-result response may be legitimate, but never silently erase an existing feed.
    if not rows:raise ValueError("No verified injuries returned; existing output retained")
    for subdir in ("","next"):
        save(subdir,"injuries.json",{"status":"verified","source":"ESPN","injuries":rows})
    print(f"NHL injuries: {len(rows)} verified reports",flush=True)

def _name(value):
    return value.get("default","") if isinstance(value,dict) else str(value or "")

def build_nhl_career_stats():
    """Incremental bounded cache, with full coverage required before publication."""
    path=DATA/"career_player_cache.json"
    try:cache=json.loads(path.read_text())
    except (OSError,ValueError):cache={}
    try:current=json.loads((DATA/"players.json").read_text())
    except (OSError,ValueError):return
    skaters=current.get("players") or []
    goalies=current.get("goalies") or []
    all_players={str(p["player_id"]):p for p in skaters+goalies if p.get("player_id")}
    missing=[pid for pid in all_players if pid not in cache]
    limit=max(0,int(os.getenv("NHL_CAREER_FETCH_LIMIT","45")))
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs={pool.submit(fetch,f"player/{pid}/landing"):pid for pid in missing[:limit]}
        for job in as_completed(jobs):
            pid=jobs[job]
            try:
                payload=job.result()
                seasons=(payload.get("seasonTotals") or [])
                nhl=[s for s in seasons if s.get("leagueAbbrev")=="NHL" and s.get("gameTypeId")==2]
                if not nhl:continue
                # Prefer explicit career totals if the endpoint supplies them.
                def total(key):return sum(float(s.get(key) or 0) for s in nhl)
                games=int(total("gamesPlayed"))
                if not games:continue
                base=all_players[pid]
                if base.get("position")=="G" or pid in {str(g.get("player_id")) for g in goalies}:
                    saves=int(total("saves"));shots=int(total("shotsAgainst"));ga=int(total("goalsAgainst"))
                    cache[pid]={"player_id":pid,"name":base.get("name"),"team":base.get("team"),"position":"G","games":games,
                                "saves":saves,"shots_against":shots,"goals_against":ga,
                                "save_percentage":round(saves/shots,3) if shots else None,
                                "goals_against_per_appearance":round(ga/games,2)}
                else:
                    goals=int(total("goals"));shots=int(total("shots"))
                    cache[pid]={"player_id":pid,"name":base.get("name"),"team":base.get("team"),"position":base.get("position"),
                                "games":games,"goals":goals,"assists":int(total("assists")),
                                "points":int(total("points")),"shots":shots,
                                "goals_per_game":round(goals/games,3),"shots_per_game":round(shots/games,3)}
            except Exception as exc:print(f"NHL career {pid}: {exc}",flush=True)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(cache,ensure_ascii=False),encoding="utf-8")
    covered=[pid for pid in all_players if pid in cache]
    if len(covered)<len(all_players):
        print(f"NHL career cache: {len(covered)}/{len(all_players)} players; awaiting complete coverage",flush=True)
        return
    save("","players_career.json",{"players":[cache[pid] for pid in all_players if cache[pid].get("position")!="G"],
                                    "goalies":[cache[pid] for pid in all_players if cache[pid].get("position")=="G"]})
    print(f"NHL career totals published for {len(covered)} players",flush=True)

def build_nhl_matchup_history(slates):
    """Complete head-to-head results for two seasons from official club schedules."""
    now=datetime.now(ZoneInfo("America/Chicago"))
    start=now.year if now.month>=9 else now.year-1
    seasons=(f"{start}{start+1}",f"{start-1}{start}")
    teams=sorted({g[side] for _,games in slates for g in games for side in ("away","home") if g.get(side)})
    if not teams:return
    results={}
    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs={pool.submit(fetch,f"club-schedule-season/{team}/{season}"):(team,season) for team in teams for season in seasons}
        for job in as_completed(jobs):
            team,season=jobs[job]
            try:
                payload=job.result()
                if not isinstance(payload.get("games"),list):continue
                for g in payload["games"]:
                    if g.get("gameState") not in ("FINAL","OFF"):continue
                    a=g.get("awayTeam") or {};h=g.get("homeTeam") or {}
                    away=a.get("abbrev");home=h.get("abbrev")
                    if not away or not home or a.get("score") is None or h.get("score") is None:continue
                    gid=str(g.get("id") or "")
                    if gid:results[gid]={"id":g.get("id"),"date":g.get("gameDate"),"away":away,"home":home,
                                        "away_score":a["score"],"home_score":h["score"]}
            except Exception as exc:print(f"NHL schedule {team} {season}: {exc}",flush=True)
    if not results:raise ValueError("No verified final games in NHL schedules")
    lookup=defaultdict(list)
    for game in results.values():
        lookup[tuple(sorted((game["away"],game["home"])))].append(game)
    for games in lookup.values():games.sort(key=lambda g:g["date"] or "",reverse=True)
    for subdir,games in slates:
        save(subdir,"matchup_history.json",{"games":[{"game_id":g["game_id"],"games":lookup.get(tuple(sorted((g["away"],g["home"]))),[])[:10]} for g in games]})
    print(f"NHL matchup history: {len(results)} completed games across {len(teams)} scheduled teams",flush=True)
