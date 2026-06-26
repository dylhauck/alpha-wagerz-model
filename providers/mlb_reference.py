import requests
from pathlib import Path
import pandas as pd

TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams?sportId=1"
OUTPUT_DIR = Path("data/reference")


def get_mlb_teams():
    response = requests.get(TEAMS_URL)
    response.raise_for_status()
    data = response.json()

    rows = []

    for team in data.get("teams", []):
        venue = team.get("venue", {})

        rows.append({
            "team_id": team.get("id"),
            "team_name": team.get("name"),
            "team_abbr": team.get("abbreviation"),
            "short_name": team.get("shortName"),
            "club_name": team.get("clubName"),
            "league": team.get("league", {}).get("name"),
            "division": team.get("division", {}).get("name"),
            "venue_id": venue.get("id"),
            "venue_name": venue.get("name"),
        })

    return rows


def build_reference_files():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    teams = get_mlb_teams()
    df = pd.DataFrame(teams)

    df.to_csv(OUTPUT_DIR / "mlb_teams.csv", index=False)

    stadiums = df[[
        "team_id",
        "team_name",
        "team_abbr",
        "venue_id",
        "venue_name",
    ]].drop_duplicates()

    stadiums.to_csv(OUTPUT_DIR / "stadiums.csv", index=False)

    print(f"✅ Saved {len(df)} MLB teams")
    print("📁 data/reference/mlb_teams.csv")
    print("📁 data/reference/stadiums.csv")


if __name__ == "__main__":
    build_reference_files()