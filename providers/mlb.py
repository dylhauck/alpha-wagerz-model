import requests
from datetime import date

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"


def get_probable_pitcher(team_data):
    pitcher = team_data.get("probablePitcher") or {}

    return {
        "name": pitcher.get("fullName", ""),
        "id": pitcher.get("id", ""),
    }


def get_todays_slate():
    today = date.today().isoformat()

    params = {
        "sportId": 1,
        "date": today,
        "hydrate": "probablePitcher,venue,team,linescore",
    }

    response = requests.get(MLB_SCHEDULE_URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    games = []

    for day in data.get("dates", []):
        for game in day.get("games", []):
            away_team_data = game["teams"]["away"]
            home_team_data = game["teams"]["home"]

            away = away_team_data["team"]["name"]
            home = home_team_data["team"]["name"]

            away_pitcher = get_probable_pitcher(away_team_data)
            home_pitcher = get_probable_pitcher(home_team_data)

            games.append({
                "game_id": game["gamePk"],
                "date": today,
                "game": f"{away} @ {home}",

                "away_team": away,
                "home_team": home,

                "away_sp": away_pitcher["name"],
                "away_sp_id": away_pitcher["id"],

                "home_sp": home_pitcher["name"],
                "home_sp_id": home_pitcher["id"],

                "venue": game.get("venue", {}).get("name", ""),
                "status": game.get("status", {}).get("detailedState", ""),
            })

    return games


if __name__ == "__main__":
    from utils.file_utils import save_json

    slate = get_todays_slate()
    save_json(slate, "data/raw/todays_slate.json")

    print(f"Saved {len(slate)} games to data/raw/todays_slate.json")