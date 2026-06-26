import requests
from datetime import date
from pathlib import Path
from utils.file_utils import save_json

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
OUTPUT_FILE = Path("data/processed/lineups.json")


def get_official_lineups():
    today = date.today().isoformat()

    params = {
        "sportId": 1,
        "date": today,
        "hydrate": "lineups,team,probablePitcher,venue",
    }

    response = requests.get(MLB_SCHEDULE_URL, params=params)
    response.raise_for_status()

    data = response.json()
    lineups = []

    for day in data.get("dates", []):
        for game in day.get("games", []):
            game_id = str(game["gamePk"])
            away_team = game["teams"]["away"]["team"]["name"]
            home_team = game["teams"]["home"]["team"]["name"]

            away_lineup = game["teams"]["away"].get("lineup", [])
            home_lineup = game["teams"]["home"].get("lineup", [])

            lineup_status = "confirmed" if away_lineup and home_lineup else "unconfirmed"

            lineups.append({
                "game_id": game_id,
                "game": f"{away_team} @ {home_team}",
                "lineup_status": lineup_status,
                "away_team": away_team,
                "home_team": home_team,
                "away_hitters": away_lineup,
                "home_hitters": home_lineup,
            })

    save_json(lineups, OUTPUT_FILE)

    print(f"✅ Saved lineups for {len(lineups)} games")
    print(f"📁 {OUTPUT_FILE}")

    return lineups


if __name__ == "__main__":
    get_official_lineups()