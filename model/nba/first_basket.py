"""NBA first-field-goal model from verified ESPN opening play-by-play.

Never substitute season points-per-game for observed first-shot frequency.
An unavailable source produces an unavailable forecast, not invented odds.
"""
from __future__ import annotations

import json
import math
import os
import shutil
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "processed" / "nba"
WEB = ROOT.parent / "alpha-wagerz-web" / "public" / "data" / "nba"
HISTORY = DATA / "first_basket_history.json"
BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
TIMEOUT = 9


def read(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch(url):
    response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "AlphaWagerz/1.0"})
    response.raise_for_status()
    return response.json()


def get_events(day):
    payload = fetch(f"{BASE}/scoreboard?dates={day:%Y%m%d}&limit=100")
    return [
        str(event["id"])
        for event in payload.get("events", [])
        if event.get("status", {}).get("type", {}).get("completed")
        and event.get("id")
    ]


def athlete_id(play):
    athlete = play.get("athlete") or {}
    if isinstance(athlete, dict) and athlete.get("id"):
        return str(athlete["id"])
    participants = play.get("participants") or []
    if participants:
        first = participants[0]
        if isinstance(first, dict):
            a = first.get("athlete") or {}
            if a.get("id"):
                return str(a["id"])
    return ""


def team_id(play):
    team = play.get("team") or {}
    return str(team.get("id") or "") if isinstance(team, dict) else ""


def opening_events(game_id):
    payload = fetch(f"{BASE}/summary?event={game_id}")
    plays = payload.get("plays") or []
    if isinstance(plays, dict):
        plays = plays.get("items") or []
    if not isinstance(plays, list) or not plays:
        return None
    competitors = (
        ((payload.get("header") or {}).get("competitions") or [{}])[0]
        .get("competitors") or []
    )
    teams = {}
    for comp in competitors:
        team = comp.get("team") or {}
        if team.get("id") and team.get("abbreviation"):
            teams[str(team["id"])] = str(team["abbreviation"]).upper()
    if len(teams) != 2:
        return None
    athletes = {}
    starters = {}
    for group in (payload.get("boxscore") or {}).get("players") or []:
        team = group.get("team") or {}
        tid = str(team.get("id") or "")
        if tid not in teams:
            continue
        starters[tid] = []
        for stat_group in group.get("statistics") or []:
            for entry in stat_group.get("athletes") or []:
                athlete = entry.get("athlete") or {}
                pid = str(athlete.get("id") or "")
                name = athlete.get("displayName") or athlete.get("fullName")
                if pid and name:
                    athletes[pid] = name
                    if entry.get("starter") is True:
                        starters[tid].append(pid)
    if any(len(starters.get(tid, [])) != 5 for tid in teams):
        return None
    first_shots = {}
    first_made = None
    tip_winner = None
    for play in plays:
        if int((play.get("period") or {}).get("number") or 0) != 1:
            continue
        kind = str((play.get("type") or {}).get("text") or "").lower()
        description = str(play.get("text") or "").lower()
        team = team_id(play)
        athlete = athlete_id(play)
        if tip_winner is None and ("jump ball" in kind or "jump ball" in description):
            if "wins tip" in description and team in teams:
                tip_winner = team
        if not team or not athlete:
            continue
        free_throw = "free throw" in kind or "free throw" in description
        made = ("made" in kind or "makes" in description) and not free_throw
        missed = ("missed" in kind or "misses" in description) and not free_throw
        if not (made or missed):
            continue
        if team not in first_shots:
            first_shots[team] = {"player": athlete, "made": made}
        if made:
            first_made = {"player": athlete, "team": team}
            break
    if not first_made or not first_shots:
        return None
    return {"teams": teams, "starters": starters, "athletes": athletes,
            "first_shots": first_shots, "first_made": first_made,
            "tip_winner": tip_winner}

def update_history():
    saved = read(HISTORY)
    games = saved.get("games", {}) if isinstance(saved.get("games"), dict) else {}
    today = datetime.now(timezone.utc).date()
    # Initial backfill: 28 days, then incrementally cache results each day.
    # Strict cap prevents the daily workflow from stalling on ESPN.
    ids = []
    for days_ago in range(1, 29):
        day = today - timedelta(days=days_ago)
        try:
            ids.extend(get_events(day))
        except (requests.RequestException, ValueError, KeyError) as exc:
            print(f"  First basket scoreboard {day}: {exc}", flush=True)
    missing = [game for game in dict.fromkeys(ids) if game not in games][:100]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(opening_events, game): game for game in missing}
        for future in as_completed(futures):
            game = futures[future]
            try:
                record = future.result()
                if record:
                    games[game] = record
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                print(f"  First basket game {game}: {exc}", flush=True)
    save(HISTORY, {"source": "ESPN NBA play-by-play", "games": games})
    return games


def player_lookup():
    payload = read(DATA / "players.json")
    rows = payload if isinstance(payload, list) else payload.get("players", [])
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("player_id", "id", "espn_id"):
            if row.get(key):
                result[str(row[key])] = row
    return result


def normalized_name(value):
    import unicodedata
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", str(value or "").lower())
        if ch.isalnum()
    )


def candidate_rows(game, matchup, history, roster):
    players = []
    for side in ("away", "home"):
        for player in matchup.get(f"{side}_players", []):
            if not isinstance(player, dict):
                continue
            current = (player.get("splits") or {}).get("current_season") or {}
            if not current.get("games") or not current.get("min_per_game"):
                continue
            players.append({
                "player_id": player.get("player_id"),
                "player_name": player.get("player_name"),
                "team": game.get(f"{side}_abbr") or game.get(f"{side}_team"),
                "side": side,
                "minutes": float(current.get("min_per_game") or 0),
                "fg_pct": float(current.get("fg_pct") or 0),
            })
    starters = []
    for side in ("away", "home"):
        starters += sorted(
            [p for p in players if p["side"] == side],
            key=lambda p: p["minutes"], reverse=True,
        )[:5]
    if len(starters) != 10:
        return [], "incomplete projected starting lineup"
    return starters, None


def make_forecast(game, matchup, history, roster):
    starters, error = candidate_rows(game, matchup, history, roster)
    base = {
        "game_id": game.get("game_id"),
        "away_team": game.get("away_abbr") or game.get("away_team"),
        "home_team": game.get("home_abbr") or game.get("home_team"),
        "lineup_status": "projected_by_minutes",
        "source": "ESPN NBA play-by-play",
        "history_games": len(history), "players": [],
        "status": "unavailable", "reason": error,
    }
    if error:
        return base
    # Historical denominators must be games where this athlete ACTUALLY
    # started; never divide by unrelated league games.
    counts = defaultdict(lambda: {"starts": 0, "first_shots": 0,
                                  "first_baskets": 0})
    for record in history.values():
        team_abbrs = record.get("teams") or {}
        actual_starters = record.get("starters") or {}
        athletes = record.get("athletes") or {}
        first_made = str((record.get("first_made") or {}).get("player") or "")
        first_shots = {
            str(x.get("player") or "")
            for x in (record.get("first_shots") or {}).values()
        }
        for tid, starter_ids in actual_starters.items():
            team = str(team_abbrs.get(tid) or "")
            for pid in starter_ids:
                name = normalized_name(athletes.get(pid))
                if not name:
                    continue
                key = (team, name)
                counts[key]["starts"] += 1
                counts[key]["first_shots"] += int(pid in first_shots)
                counts[key]["first_baskets"] += int(pid == first_made)
    observed = []
    for player in starters:
        key = (str(player["team"]).upper(), normalized_name(player["player_name"]))
        stats = counts[key]
        if stats["starts"] < 3:
            base["reason"] = (
                "Insufficient verified opening-play history for all ten projected starters"
            )
            return base
        observed.append((player, stats))
    # Empirical Bayes smoothing with a 10% prior per starter.
    # Probabilities are normalized across the ten candidates because
    # exactly one player scores the game's first made field goal.
    raw = [(row["first_baskets"] + 2) / (row["starts"] + 20)
           for _, row in observed]
    denominator = sum(raw)
    if denominator <= 0:
        base["reason"] = "No usable first-field-goal observations"
        return base
    base["players"] = [
        {
            "player_id": player["player_id"],
            "player_name": player["player_name"],
            "team": player["team"],
            "probability": round(100 * raw[i] / denominator, 2),
            "first_shot_rate": round(100 * stats["first_shots"] / stats["starts"], 2),
            "first_basket_rate": round(100 * stats["first_baskets"] / stats["starts"], 2),
            "starts_sample": stats["starts"],
            "lineup_status": "projected_by_minutes",
        }
        for i, (player, stats) in enumerate(observed)
    ]
    base["players"].sort(key=lambda x: x["probability"], reverse=True)
    base["status"] = "estimated"
    base["reason"] = (
        "Small-sample, smoothed historical first-basket estimate; "
        "tip-off probability and confirmed starters not available"
    )
    return base


def build_first_basket():
    history = update_history()
    roster = player_lookup()
    for subdir in ("", "next"):
        folder = DATA / subdir
        slate = read(folder / "slate.json")
        matchups = read(folder / "player_matchups.json")
        games = slate if isinstance(slate, list) else slate.get("games", [])
        matchup_games = matchups if isinstance(matchups, list) else matchups.get("games", [])
        by_id = {str(x.get("game_id")): x for x in matchup_games}
        forecasts = []
        for game in games:
            matchup = by_id.get(str(game.get("game_id")), {})
            forecasts.append(make_forecast(game, matchup, history, roster))
        output = {"generated_at": datetime.now(timezone.utc).isoformat(),
                  "slate_type": subdir or "current",
                  "games": forecasts}
        target = folder / "first_basket.json"
        save(target, output)
        destination = WEB / subdir / "first_basket.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
        print(f"  NBA first basket {subdir or 'current'}: {len(forecasts)} games, "
              f"{len(history)} verified historical games", flush=True)


if __name__ == "__main__":
    build_first_basket()
