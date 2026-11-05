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
    """Build per-player history against each opponent from verified cached NHL boxscores.

    Does not substitute team-v-team final scores for player-v-opponent history.
    Cached completed games are reused, so this adds no NHL API requests.
    """
    cache_dir=DATA/"boxscore_cache"
    indexed=defaultdict(list)
    if cache_dir.exists():
        for path in cache_dir.glob("*.json"):
            try:
                box=json.loads(path.read_text(encoding="utf-8"))
                away=(box.get("awayTeam") or {}).get("abbrev")
                home=(box.get("homeTeam") or {}).get("abbrev")
                if not away or not home:continue
                date=box.get("gameDate") or ""
                rosters=box.get("playerByGameStats") or {}
                for side,team,opponent in (("awayTeam",away,home),("homeTeam",home,away)):
                    roster=rosters.get(side) or {}
                    for group in ("forwards","defense"):
                        for player in roster.get(group) or []:
                            pid=str(player.get("playerId") or "")
                            if not pid:continue
                            name=_name(player.get("name"))
                            indexed[(team,opponent,pid)].append({
                                "date":date,"player_id":pid,"player":name,"team":team,
                                "opponent":opponent,"position":player.get("position") or "",
                                "goals":int(player.get("goals") or 0),
                                "assists":int(player.get("assists") or 0),
                                "points":int(player.get("points") or 0),
                                "shots":int(player.get("sog") or 0)})
            except (OSError,ValueError,TypeError):continue
    for subdir,games in slates:
        output=[]
        for game in games:
            away,home=game["away"],game["home"]
            rows=[]
            for (team,opponent,pid),appearances in indexed.items():
                if (team,opponent) not in ((away,home),(home,away)):continue
                n=len(appearances)
                rows.append({"player_id":pid,"player":appearances[-1]["player"],
                             "team":team,"opponent":opponent,"position":appearances[-1]["position"],
                             "games":n,"goals":sum(p["goals"] for p in appearances),
                             "assists":sum(p["assists"] for p in appearances),
                             "points":sum(p["points"] for p in appearances),
                             "shots":sum(p["shots"] for p in appearances),
                             "goals_per_game":round(sum(p["goals"] for p in appearances)/n,2),
                             "shots_per_game":round(sum(p["shots"] for p in appearances)/n,2)})
            rows.sort(key=lambda p:(p["points"],p["shots"]),reverse=True)
            output.append({"game_id":game["game_id"],"players":rows})
        save(subdir,"matchup_history.json",{"games":output})
    print(f"NHL player matchup history: {len(indexed)} player/opponent records from cached boxscores",flush=True)


def rebuild_nhl_goal_graphs(slates):
    """Use full-season verified player totals, not a 21-day sparse sample."""
    try:payload=json.loads((DATA/"players.json").read_text(encoding="utf-8"))
    except (OSError,ValueError):return
    players=payload.get("players") or []
    if len(players)<300:
        print(f"NHL goal graph: only {len(players)} players; keeping existing data",flush=True)
        return
    for subdir,games in slates:
        output=[]
        for game in games:
            away,home=game["away"],game["home"]
            candidates=[]
            for p in players:
                if p.get("team") not in (away,home):continue
                n=int(p.get("games") or 0)
                if n<3:continue
                goals=float(p.get("goals") or 0)
                shots=float(p.get("shots") or 0)
                # Empirical Bayes shrinkage to avoid extreme small-sample rates.
                goal_rate=(goals+1.0)/(n+5.0)
                shot_rate=(shots+12.0)/(n+5.0)
                expected=max(0.0,0.75*goal_rate+0.25*shot_rate*0.09)
                probability=100*(1-__import__("math").exp(-expected))
                candidates.append({"player_id":p.get("player_id"),"name":p.get("name"),
                                   "team":p.get("team"),"games":n,
                                   "goals_per_game":round(goals/n,3),
                                   "shots_per_game":round(shots/n,3),
                                   "goal_probability":round(probability,1),
                                   "expected_goals":round(expected,3),
                                   "source":"season_goals_shots_shrunk_poisson_baseline"})
            candidates.sort(key=lambda p:p["goal_probability"],reverse=True)
            output.append({"game_id":game["game_id"],"players":candidates})
        if any(g["players"] for g in output):
            save(subdir,"anytime_goals.json",{"games":output})
            print(f"NHL {subdir or 'current'} goal graph: {sum(len(g['players']) for g in output)} players",flush=True)
