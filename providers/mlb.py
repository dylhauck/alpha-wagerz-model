import requests
from datetime import date, datetime
from zoneinfo import ZoneInfo

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"


def format_game_time(game_date):
    if not game_date:
        return "", ""

    utc_dt = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
    central_dt = utc_dt.astimezone(ZoneInfo("America/Chicago"))

    display = central_dt.strftime("%I:%M %p").lstrip("0")
    sort = central_dt.strftime("%H:%M")

    return display, sort


def get_todays_slate():
    today = date.today().isoformat()

    params = {
        "sportId": 1,
        "date": today,
        "hydrate": "probablePitcher,venue,team",
    }

    response = requests.get(MLB_SCHEDULE_URL, params=params)
    response.raise_for_status()

    data = response.json()
    games = []

    for day in data.get("dates", []):
        for game in day.get("games", []):
            away = game["teams"]["away"]["team"]["name"]
            home = game["teams"]["home"]["team"]["name"]

            away_pitcher = game["teams"]["away"].get("probablePitcher", {}).get("fullName", "")
            home_pitcher = game["teams"]["home"].get("probablePitcher", {}).get("fullName", "")

            game_date = game.get("gameDate", "")
            game_time, game_time_sort = format_game_time(game_date)

            games.append({
                "game_id": game["gamePk"],
                "date": today,
                "game": f"{away} @ {home}",
                "away_team": away,
                "home_team": home,
                "away_sp": away_pitcher,
                "home_sp": home_pitcher,
                "venue": game.get("venue", {}).get("name", ""),
                "status": game.get("status", {}).get("detailedState", ""),
                "game_date_utc": game_date,
                "game_time": game_time,
                "game_time_sort": game_time_sort,
            })

    return games


if __name__ == "__main__":
    from utils.file_utils import save_json

    slate = get_todays_slate()
    save_json(slate, "data/raw/todays_slate.json")

    print(f"Saved {len(slate)} games to data/raw/todays_slate.json")