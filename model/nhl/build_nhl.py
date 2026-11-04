"""NHL current/next slate data, sourced from the NHL public API.

All forecasts are explicitly estimates from observed completed games.
Missing data stays missing; no placeholder odds or invented injuries.
"""
from __future__ import annotations

import json
import math
import shutil
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed" / "nhl"
WEB = ROOT.parent / "alpha-wagerz-web" / "public" / "data" / "nhl"
API = "https://api-web.nhle.com/v1"
CENTRAL = ZoneInfo("America/Chicago")


def fetch(path):
    response = requests.get(f"{API}/{path}", timeout=18,
                            headers={"User-Agent": "AlphaWagerz/1.0"})
    response.raise_for_status()
    return response.json()


def save(subdir, name, payload):
    path = DATA / subdir / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    target = WEB / subdir / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def abbreviation(team):
    return str((team or {}).get("abbrev") or "")


def team_name(team):
    name = (team or {}).get("placeName") or {}
    common = (team or {}).get("commonName") or {}
    return " ".join(str(x.get("default") or "") for x in (name, common)).strip()


def scheduled_games(day):
    data = fetch(f"schedule/{day.isoformat()}")
    games = []
    for section in data.get("gameWeek") or []:
        if section.get("date") != day.isoformat():
            continue
        for game in section.get("games") or []:
            away, home = game.get("awayTeam") or {}, game.get("homeTeam") or {}
            if not game.get("id"):
                continue
            games.append({
                "game_id": game["id"], "date": day.isoformat(),
                "start_time_utc": game.get("startTimeUTC"),
                "venue": (game.get("venue") or {}).get("default"),
                "away": abbreviation(away), "home": abbreviation(home),
                "away_name": team_name(away), "home_name": team_name(home),
                "away_logo": away.get("logo"), "home_logo": home.get("logo"),
                "status": game.get("gameState"),
                "away_score": away.get("score"), "home_score": home.get("score"),
            })
    return games


def previous_games(day, lookback=42):
    # Pull historical games from one weekly schedule call per seven days.
    completed = {}
    for days in range(1, lookback + 1, 7):
        previous = day - timedelta(days=days)
        payload = fetch(f"schedule/{previous.isoformat()}")
        for section in payload.get("gameWeek") or []:
            if not section.get("date") or section["date"] >= day.isoformat():
                continue
            for game in section.get("games") or []:
                if game.get("gameState") not in ("FINAL", "OFF"):
                    continue
                game_id = game.get("id")
                if game_id:
                    completed[str(game_id)] = {
                        "id": game_id,
                        "date": section.get("date"),
                        "away": abbreviation(game.get("awayTeam")),
                        "home": abbreviation(game.get("homeTeam")),
                        "away_score": (game.get("awayTeam") or {}).get("score"),
                        "home_score": (game.get("homeTeam") or {}).get("score"),
                    }
    return sorted(completed.values(), key=lambda row: row["date"] or "", reverse=True)


def player_history(games):
    records = defaultdict(lambda: {"games": 0, "goals": 0, "shots": 0,
                                    "assists": 0, "points": 0, "toi": 0,
                                    "team": "", "name": "", "position": "", "toi_seconds": 0})
    teams = defaultdict(lambda: {"games": 0, "goals_for": 0, "goals_against": 0,
                                 "wins": 0, "last_games": []})
    matchups = defaultdict(list)
    boxscores = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch, f"gamecenter/{game['id']}/boxscore"): str(game['id']) for game in games[:140]}
        for future in as_completed(futures):
            try:
                boxscores[futures[future]] = future.result()
            except (requests.RequestException, ValueError) as exc:
                print(f"  NHL boxscore {futures[future]} unavailable: {exc}", flush=True)
    for game in games:
        a, h = game["away"], game["home"]
        ag, hg = game.get("away_score"), game.get("home_score")
        if ag is not None and hg is not None:
            for code, scored, conceded in ((a, ag, hg), (h, hg, ag)):
                t = teams[code]
                t["games"] += 1
                t["goals_for"] += scored
                t["goals_against"] += conceded
                t["wins"] += int(scored > conceded)
                t["last_games"].append({"opponent": h if code == a else a,
                                         "goals_for": scored, "goals_against": conceded,
                                         "date": game["date"]})
            matchups[tuple(sorted((a, h)))].append(game)
        box = boxscores.get(str(game["id"]))
        if not box:
            continue
        for side, team in (("awayTeam", a), ("homeTeam", h)):
            roster = ((box.get("playerByGameStats") or {}).get("awayTeam" if side == "awayTeam" else "homeTeam") or {})
            for group in ("forwards", "defense"):
                for p in roster.get(group) or []:
                    pid = str(p.get("playerId") or "")
                    if not pid:
                        continue
                    row = records[pid]
                    row["games"] += 1
                    row["goals"] += int(number(p.get("goals")))
                    row["shots"] += int(number(p.get("sog")))
                    row["assists"] += int(number(p.get("assists")))
                    row["points"] += int(number(p.get("points")))
                    toi = str(p.get("toi") or "0:00").split(":")
                    if len(toi) == 2:
                        row["toi_seconds"] += int(number(toi[0])) * 60 + int(number(toi[1]))
                    row["team"] = team
                    row["position"] = str(p.get("position") or "")
                    name = p.get("name") or {}
                    row["name"] = name.get("default") if isinstance(name, dict) else str(name)
    return records, teams, matchups


def build_nhl():
    today = datetime.now(CENTRAL).date()
    today_games = scheduled_games(today)
    tomorrow_games = scheduled_games(today + timedelta(days=1))
    history_games = previous_games(today)
    player_stats, team_stats, head_to_head = player_history(history_games)
    player_rows = []
    for pid, p in player_stats.items():
        n = p["games"]
        if n == 0:
            continue
        player_rows.append({
            "player_id": pid, "name": p["name"], "team": p["team"],
            "position": p["position"], "games": n,
            "goals": p["goals"], "assists": p["assists"],
            "points": p["points"], "shots": p["shots"],
            "goals_per_game": round(p["goals"] / n, 3),
            "shots_per_game": round(p["shots"] / n, 3),
            "toi_minutes_per_game": round(p["toi_seconds"] / n / 60, 2),
        })
    player_rows.sort(key=lambda p: (p["goals_per_game"], p["shots_per_game"]), reverse=True)
    team_rows = []
    for team, t in team_stats.items():
        n = t["games"]
        if not n:
            continue
        team_rows.append({
            "team": team, "games": n, "wins": t["wins"],
            "goals_for_per_game": round(t["goals_for"] / n, 2),
            "goals_against_per_game": round(t["goals_against"] / n, 2),
        })
    team_rows.sort(key=lambda t: t["goals_for_per_game"], reverse=True)

    for subdir, games in (("", today_games), ("next", tomorrow_games)):
        projections = []
        goal_graphs = []
        histories = []
        for game in games:
            away, home = game["away"], game["home"]
            ta, th = team_stats.get(away), team_stats.get(home)
            away_goals = (
                (ta["goals_for"] / ta["games"] + th["goals_against"] / th["games"]) / 2
                if ta and th and ta["games"] and th["games"] else None
            )
            home_goals = (
                (th["goals_for"] / th["games"] + ta["goals_against"] / ta["games"]) / 2
                if ta and th and ta["games"] and th["games"] else None
            )
            projections.append({
                "game_id": game["game_id"], "away": away, "home": home,
                "away_goals": round(away_goals, 2) if away_goals is not None else None,
                "home_goals": round(home_goals, 2) if home_goals is not None else None,
                "model": "recent_goals_for_against_baseline",
                "sample_games": min(ta["games"], th["games"]) if ta and th else 0,
            })
            candidates = []
            for p in player_rows:
                if p["team"] not in (away, home) or p["games"] < 3:
                    continue
                own = away_goals if p["team"] == away else home_goals
                t = team_stats.get(p["team"])
                if own is None or not t or not t["games"]:
                    continue
                team_rate = t["goals_for"] / t["games"]
                adjustment = max(0.65, min(1.35, own / team_rate)) if team_rate else 1.0
                # Shrink noisy recent scoring towards shots-based scoring
                # opportunity; the prior is explicitly heuristic.
                shooting_rate = (p["goals"] + 1.5) / (p["shots"] + 15) if p["shots"] else 0.09
                shot_based = p["shots_per_game"] * shooting_rate
                expected = (0.65 * p["goals_per_game"] + 0.35 * shot_based) * adjustment
                candidates.append({
                    "player_id": p["player_id"], "name": p["name"], "team": p["team"],
                    "games": p["games"], "goals_per_game": p["goals_per_game"],
                    "shots_per_game": p["shots_per_game"],
                    "toi_minutes_per_game": p["toi_minutes_per_game"],
                    "goal_probability": round(100 * (1 - math.exp(-expected)), 1),
                    "expected_goals": round(expected, 3),
                    "source": "recent_goals_shots_shrinkage_poisson_baseline",
                })
            candidates.sort(key=lambda p: p["goal_probability"], reverse=True)
            goal_graphs.append({"game_id": game["game_id"], "players": candidates})
            histories.append({
                "game_id": game["game_id"],
                "games": head_to_head.get(tuple(sorted((away, home))), [])[:10],
            })
        save(subdir, "slate.json", {"date": (today + (timedelta(days=1) if subdir else timedelta())).isoformat(), "games": games})
        save(subdir, "projections.json", {"games": projections})
        save(subdir, "anytime_goals.json", {"games": goal_graphs})
        save(subdir, "matchup_history.json", {"games": histories})
        save(subdir, "players.json", {"players": player_rows})
        save(subdir, "teams.json", {"teams": team_rows})
        save(subdir, "injuries.json", {"status": "unavailable", "injuries": [],
                                       "message": "Verified NHL injury feed not connected."})
        print(f"  NHL {subdir or 'current'}: {len(games)} games, {len(player_rows)} historical skaters", flush=True)


if __name__ == "__main__":
    build_nhl()
