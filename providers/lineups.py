import requests
from pathlib import Path

from model.game_selector import get_game_index
from utils.file_utils import save_json

OUTPUT_FILE = Path("data/processed/lineups.json")


def get_json(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.json()


def hitter_from_player(player, team_name):
    person = player.get("person", {})
    return {
        "id": person.get("id"),
        "name": person.get("fullName"),
        "team": team_name,
    }


def get_roster_hitters(team_id, team_name):
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster/active"
    data = get_json(url)

    hitters = []

    for player in data.get("roster", []):
        position = player.get("position", {}).get("abbreviation", "")

        if position == "P":
            continue

        hitters.append(hitter_from_player(player, team_name))

    return hitters


def get_boxscore_lineup(game_id):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/boxscore"
    data = get_json(url)

    result = {}

    for side in ["away", "home"]:
        team = data["teams"][side]["team"]
        team_name = team["name"]
        team_id = team["id"]
        players = data["teams"][side].get("players", {})

        lineup = []

        for player_key, player in players.items():
            batting_order = player.get("battingOrder")

            if batting_order:
                person = player.get("person", {})
                lineup.append({
                    "id": person.get("id"),
                    "name": person.get("fullName"),
                    "team": team_name,
                    "batting_order": int(batting_order),
                })

        lineup.sort(key=lambda x: x["batting_order"])

        if lineup:
            status = "confirmed"
            hitters = lineup
        else:
            status = "roster_fallback"
            hitters = get_roster_hitters(team_id, team_name)

        result[side] = {
            "team_id": team_id,
            "team_name": team_name,
            "lineup_status": status,
            "hitters": hitters,
        }

    return result


def build_lineups():
    games = get_game_index()
    lineups = []

    for game in games:
        game_id = game["game_id"]

        try:
            data = get_boxscore_lineup(game_id)

            away_status = data["away"]["lineup_status"]
            home_status = data["home"]["lineup_status"]

            lineup_status = (
                "confirmed"
                if away_status == "confirmed" and home_status == "confirmed"
                else "roster_fallback"
            )

            lineups.append({
                "game_id": str(game_id),
                "game": game["game"],
                "lineup_status": lineup_status,
                "away_team": data["away"]["team_name"],
                "home_team": data["home"]["team_name"],
                "away_team_id": data["away"]["team_id"],
                "home_team_id": data["home"]["team_id"],
                "away_hitters": data["away"]["hitters"],
                "home_hitters": data["home"]["hitters"],
            })

            print(f"✅ {game['game']} — {lineup_status}")

        except Exception as e:
            print(f"⚠️ Failed lineup for {game['game']}: {e}")

    save_json(lineups, OUTPUT_FILE)

    print(f"📁 Saved lineups to {OUTPUT_FILE}")
    return lineups


if __name__ == "__main__":
    build_lineups()