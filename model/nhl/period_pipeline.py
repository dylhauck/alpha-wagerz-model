"""NHL period scoring model using observed period scores from completed NHL games.

No equal-third splitting: periods are learned from actual gamecenter landing
linescores. Missing periods remain null. Reuses the existing 21-day game list.
"""
from __future__ import annotations
import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from .build_nhl import DATA, fetch, save

PERIODS=("1st Period","2nd Period","3rd Period")
CACHE=DATA/"period_score_cache.json"

def _period_scores(payload):
    """Read period goal counts from NHL gamecenter landing responses.

    The landing endpoint exposes summary.scoring as a list of period objects
    with individual goal events. It does not consistently include linescore.
    """
    summary=payload.get("summary") or {}
    scoring=summary.get("scoring") or []
    if isinstance(scoring,list):
        result=[]
        for idx,period in enumerate(scoring[:3],1):
            if not isinstance(period,dict): continue
            descriptor=period.get("periodDescriptor") or {}
            number=descriptor.get("number") or period.get("period") or idx
            if number not in (1,2,3): continue
            goals=period.get("goals")
            if not isinstance(goals,list): continue
            away=sum(1 for goal in goals if goal.get("teamAbbrev") == payload.get("awayTeam",{}).get("abbrev"))
            home=sum(1 for goal in goals if goal.get("teamAbbrev") == payload.get("homeTeam",{}).get("abbrev"))
            # The scoring list is complete for a final game, including
            # scoreless periods (goals=[]).
            result.append((number,away,home))
        if len(result)==3:
            return result
    lines=summary.get("linescore") or payload.get("linescore") or {}
    entries=lines.get("byPeriod") or lines.get("periods") or []
    result=[]
    for period in entries:
        descriptor=period.get("periodDescriptor") or {}
        index=descriptor.get("number") or period.get("period")
        if index not in (1,2,3): continue
        away=period.get("away")
        home=period.get("home")
        if isinstance(away,dict): away=away.get("goals")
        if isinstance(home,dict): home=home.get("goals")
        if isinstance(away,int) and isinstance(home,int):
            result.append((index,away,home))
    return result

def build_period_projections(history_games,slates,max_fetch=36):
    try: cache=json.loads(CACHE.read_text()) if CACHE.exists() else {}
    except (OSError,ValueError): cache={}
    pending=[g for g in history_games if str(g["id"]) not in cache][:max_fetch]
    with ThreadPoolExecutor(max_workers=6) as pool:
        tasks={pool.submit(fetch,f'gamecenter/{g["id"]}/landing'):g for g in pending}
        for task in as_completed(tasks):
            game=tasks[task]
            try:
                scores=_period_scores(task.result())
                if len(scores)==3: cache[str(game["id"])]=scores
            except Exception as exc:
                print(f'NHL period history {game["id"]} unavailable: {exc}',flush=True)
    CACHE.parent.mkdir(parents=True,exist_ok=True)
    CACHE.write_text(json.dumps(cache),encoding="utf-8")
    team_periods=defaultdict(lambda:defaultdict(lambda:{"gf":0,"ga":0,"n":0}))
    for game in history_games:
        scores=cache.get(str(game["id"])) or []
        for index,away,home in scores:
            for team,gf,ga in ((game["away"],away,home),(game["home"],home,away)):
                stats=team_periods[team][index]
                stats["gf"]+=gf;stats["ga"]+=ga;stats["n"]+=1
    for subdir,games in slates:
        output=[]
        for game in games:
            periods={}
            for i,label in enumerate(PERIODS,1):
                a=team_periods[game["away"]][i]
                h=team_periods[game["home"]][i]
                if min(a["n"],h["n"])<1:
                    periods[label]={"away_goals":None,"home_goals":None,"sample_games":min(a["n"],h["n"])}
                    continue
                # Shrink small observed samples toward a league-wide period
                # scoring prior instead of suppressing every projection.
                # This is a model estimate, not a sportsbook line.
                league_gf = sum(t[i]["gf"] for t in team_periods.values())
                league_n = sum(t[i]["n"] for t in team_periods.values())
                prior = league_gf / league_n if league_n else 1.0
                shrink = 5.0
                away_attack = (a["gf"] + shrink * prior) / (a["n"] + shrink)
                away_defense = (a["ga"] + shrink * prior) / (a["n"] + shrink)
                home_attack = (h["gf"] + shrink * prior) / (h["n"] + shrink)
                home_defense = (h["ga"] + shrink * prior) / (h["n"] + shrink)
                away = (away_attack + home_defense) / 2
                home = (home_attack + away_defense) / 2
                periods[label]={"away_goals":round(away,3),"home_goals":round(home,3),"sample_games":min(a["n"],h["n"])}
            output.append({"game_id":game["game_id"],"away":game["away"],"home":game["home"],"periods":periods})
        save(subdir,"period_projections.json",{"model":"observed_period_scoring_baseline","games":output})
    print(f'NHL period model: {len(cache)} completed games with period linescores',flush=True)
