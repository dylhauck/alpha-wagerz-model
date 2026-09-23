import requests
from pathlib import Path
import pandas as pd
from utils.file_utils import save_json

TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
OUTPUT_JSON = Path("data/processed/mlb/player_reference.json")
OUTPUT_CSV = Path("data/reference/mlb/player_reference.csv")

# MLB Stats API supports hydrating roster people in the roster response.
# This removes the old one-request-per-player detail lookup.
ROSTER_HYDRATE = "person(batSide,pitchHand)"


def get_json(url, params=None):
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def get_teams():
    data = get_json(TEAMS_URL)
    return data.get("teams", [])


def get_team_roster(team_id):
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster/active"
    data = get_json(
        url,
        params={"hydrate": ROSTER_HYDRATE},
    )
    return data.get("roster", [])


def build_player_reference():
    players = []

    for team in get_teams():
        team_id = team.get("id")
        team_name = team.get("name")
        team_abbr = team.get("abbreviation")

        try:
            roster = get_team_roster(team_id)
        except Exception as e:
            print(f"⚠️ Failed roster for {team_name}: {e}")
            continue

        for item in roster:
            person = item.get("person", {})
            position = item.get("position", {})

            players.append({
                "player_id": person.get("id"),
                "player_name": person.get("fullName"),
                "team_id": team_id,
                "team_name": team_name,
                "team_abbr": team_abbr,
                "position": position.get("abbreviation"),
                "position_name": position.get("name"),
                "bats": person.get("batSide", {}).get("code", ""),
                "throws": person.get("pitchHand", {}).get("code", ""),
            })

        print(f"✅ Loaded roster: {team_name}")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(players).to_csv(OUTPUT_CSV, index=False)
    save_json(players, OUTPUT_JSON)

    print(f"✅ Saved player reference: {len(players)} players")
    print(f"📁 {OUTPUT_JSON}")
    print(f"📁 {OUTPUT_CSV}")

    return players


if __name__ == "__main__":
    build_player_reference()



