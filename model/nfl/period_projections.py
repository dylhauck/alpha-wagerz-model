"""NFL quarter/half projections from observed nflverse play-by-play scoring.

Uses end-of-quarter score changes, never divides full-game projections by four.
Requires nflreadpy (already used by NFL pipeline). Missing data stays null.
"""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import json
import math
import nflreadpy as nfl
from utils.json_utils import save_json

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"data"/"processed"/"nfl"
WEB=ROOT.parent/"alpha-wagerz-web"/"public"/"data"/"nfl"
PERIODS={"Q1":[1],"Q2":[2],"1st Half":[1,2],"Q3":[3],"Q4":[4],"2nd Half":[3,4]}

def _load(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return {}

def _games(payload):
    if isinstance(payload,list):return payload
    return payload.get("games") or payload.get("slate") or []

def _team(game,side):
    value=game.get(side) or game.get(side+"_team") or game.get(side+"Team") or ""
    if isinstance(value,dict):value=value.get("abbr") or value.get("team") or value.get("abbreviation") or ""
    return str(value).upper()

def build_nfl_period_projections():
    season=2026
    # One nflreadpy call; avoid additional network requests per game.
    frame=nfl.load_pbp([season])
    columns=["game_id","qtr","home_team","away_team","total_home_score","total_away_score"]
    rows=frame.select(columns).to_dicts()
    # Last recorded score for each quarter of each completed game.
    snapshots={}
    for row in rows:
        q=row.get("qtr")
        if q not in (1,2,3,4):continue
        key=(row.get("game_id"),int(q))
        hs=row.get("total_home_score");a=row.get("total_away_score")
        if hs is None or a is None:continue
        snapshots[key]=(row.get("home_team"),row.get("away_team"),float(hs),float(a))
    # Empirical quarter margins establish a data-derived uncertainty scale.
    margins=defaultdict(list)
    for gid in {gid for gid,q in snapshots if (gid,4) in snapshots}:
        prev=(0.0,0.0)
        for q in (1,2,3,4):
            entry=snapshots.get((gid,q))
            if not entry:continue
            _,_,hs,aw=entry
            margins[q].append((hs-prev[0])-(aw-prev[1]))
            prev=(hs,aw)
    rates=defaultdict(lambda:defaultdict(lambda:{"for":0.0,"against":0.0,"n":0}))
    game_ids={gid for gid,q in snapshots if (gid,4) in snapshots}
    for gid in game_ids:
        prev_home=prev_away=0.0
        for q in (1,2,3,4):
            entry=snapshots.get((gid,q))
            if not entry:continue
            home,away,hs,aw=entry
            if hs<prev_home or aw<prev_away:continue
            home_points=hs-prev_home;away_points=aw-prev_away
            prev_home,prev_away=hs,aw
            for team,scored,allowed in ((home,home_points,away_points),(away,away_points,home_points)):
                stat=rates[team][q];stat["for"]+=scored;stat["against"]+=allowed;stat["n"]+=1
    for subdir in ("","next"):
        slate=_games(_load(OUT/subdir/"slate.json"))
        result=[]
        for game in slate:
            away=_team(game,"away");home=_team(game,"home")
            periods={}
            for label,quarters in PERIODS.items():
                vals=[]
                for q in quarters:
                    a=rates[away][q];h=rates[home][q]
                    if min(a["n"],h["n"])<3:break
                    vals.append(((a["for"]/a["n"]+h["against"]/h["n"])/2,
                                 (h["for"]/h["n"]+a["against"]/a["n"])/2))
                if len(vals)!=len(quarters):
                    periods[label]={"away_points":None,"home_points":None,"sample_games":0}
                else:
                    away_pts=sum(x[0] for x in vals)
                    home_pts=sum(x[1] for x in vals)
                    # Estimate regulation period winner probability from observed
                    # scoring variance; ties remain possible in individual quarters.
                    variance=sum(
                        (sum((v-sum(margins[q])/len(margins[q]))**2 for v in margins[q]) /
                         max(1,len(margins[q])-1))
                        for q in quarters if len(margins[q])>=3
                    )
                    sd=math.sqrt(variance) if variance>0 else None
                    home_win=(0.5*(1+math.erf((home_pts-away_pts)/(sd*math.sqrt(2))))
                              if sd is not None else None)
                    periods[label]={"away_points":round(away_pts,2),
                                    "home_points":round(home_pts,2),
                                    "home_win_probability":round(home_win,4) if home_win is not None else None,
                                    "away_win_probability":round(1-home_win,4) if home_win is not None else None,
                                    "sample_games":min(rates[away][q]["n"] for q in quarters)}
            result.append({"game_id":game.get("game_id") or game.get("id"),"away":away,"home":home,"periods":periods})
        payload={"model":"observed_nfl_quarter_scoring_baseline","season":season,"games":result}
        for root in (OUT,WEB):
            dest=root/subdir/"period_projections.json";dest.parent.mkdir(parents=True,exist_ok=True)
            save_json(payload,dest)
    print(f'NFL quarter model: {len(game_ids)} games with quarter scores',flush=True)

if __name__=="__main__":build_nfl_period_projections()
