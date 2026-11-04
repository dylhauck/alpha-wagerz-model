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
    if not plays:
        return None
    competitors = (
        ((payload.get("header") or {}).get("competitions") or [{}])[0]
        .get("competitors") or []
    )
    teams = [str(x.get("team", {}).get("id") or x.get("id") or "") for x in competitors]
    if len(teams) != 2 or not all(teams):
        return None
    team_first_shot = {}
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
            # ESPN does not consistently encode jump-ball winners.
            # Record only when the play explicitly identifies a winning team.
            if "wins tip" in description and team in teams:
                tip_winner = team
        if not team or not athlete:
            continue
        # ESPN made/missed shot play types; explicitly exclude free throws.
        free_throw = "free throw" in kind or "free throw" in description
        made = ("made" in kind or "makes" in description) and not free_throw
        missed = ("missed" in kind or "misses" in description) and not free_throw
        if not (made or missed):
            continue
        if team not in team_first_shot:
            team_first_shot[team] = {"player": athlete, "made": made}
        if made:
            first_made = {"player": athlete, "team": team}
            break
    if not first_made or len(team_first_shot) == 0:
        return None
    return {"teams": teams, "first_shots": team_first_shot,
            "first_made": first_made, "tip_winner": tip_winner}


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


def candidate_rows(game, matchup, history, roster):
    # ESPN play-by-play athlete IDs are ESPN IDs; player_matchups may
    # contain NBA Stats IDs. Only use a verified crosswalk if present.
    players = []
    for side in ("away", "home"):
        for player in matchup.get(f"{side}_players", []):
            if not isinstance(player, dict):
                continue
            current = (player.get("splits") or {}).get("current_season") or {}
            if not current.get("games") or not current.get("min_per_game"):
                continue
            espn_id = str(player.get("espn_id") or "")
            if not espn_id:
                roster_row = roster.get(str(player.get("player_id") or ""), {})
                espn_id = str(roster_row.get("espn_id") or "")
            players.append({
                "player_id": player.get("player_id"),
                "espn_id": espn_id,
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
    if any(not p["espn_id"] for p in starters):
        return starters, "ESPN player ID crosswalk unavailable"
    return starters, None


def make_forecast(game, matchup, history, roster):
    starters, error = candidate_rows(game, matchup, history, roster)
    base = {
        "game_id": game.get("game_id"), "away_team": game.get("away_abbr") or game.get("away_team"),
        "home_team": game.get("home_abbr") or game.get("home_team"),
        "lineup_status": "projected_by_minutes",
        "source": "ESPN NBA play-by-play",
        "history_games": len(history), "players": [],
        "status": "unavailable", "reason": error,
    }
    if error:
        return base
    first = Counter()
    shots = Counter()
    starts = Counter()
    tip = Counter()
    for record in history.values():
        team_ids = record.get("teams") or []
        if len(team_ids) != 2:
            continue
        tip_winner = record.get("tip_winner")
        if tip_winner:
            tip[tip_winner] += 1
        first_made = record.get("first_made") or {}
        made_player = str(first_made.get("player") or "")
        for player in starters:
            pid = player["espn_id"]
            if pid == made_player:
                first[pid] += 1
            for shot in (record.get("first_shots") or {}).values():
                if str(shot.get("player") or "") == pid:
                    shots[pid] += 1
    # Without verified starter appearances and team ID mapping,
    # a count across all games is NOT a first-basket hit rate.
    # Do not turn these raw counts into betting probabilities.
    base["reason"] = (
        "Verified starter appearances, ESPN team mapping and opening-tip "
        "history are required before first-basket probabilities can be published"
    )
    base["observed_first_baskets"] = dict(first)
    base["observed_first_shots"] = dict(shots)
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
