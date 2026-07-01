import requests
from datetime import date
from pathlib import Path

from utils.json_utils import save_json

OUTPUT_FILE = Path("data/processed/team_context.json")

STANDINGS_URL = "https://statsapi.mlb.com/api/v1/standings"


def ordinal(n):
    try:
        n = int(n)
    except Exception:
        return ""

    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")

    return f"{n}{suffix}"


def build_team_context_file():
    season = date.today().year

    params = {
        "leagueId": "103,104",
        "season": season,
        "standingsTypes": "regularSeason",
        "hydrate": "team",
    }

    response = requests.get(STANDINGS_URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    teams = {}

    for record in data.get("records", []):
        division = record.get("division", {}).get("name", "")

        for team_record in record.get("teamRecords", []):
            team_name = team_record.get("team", {}).get("name", "")
            division_rank = team_record.get("divisionRank", "")
            games_back = team_record.get("gamesBack", "")

            teams[team_name] = {
                "team": team_name,
                "division": division,
                "division_rank": division_rank,
                "division_rank_label": ordinal(division_rank),
                "games_back": games_back,
                "wins": team_record.get("wins", ""),
                "losses": team_record.get("losses", ""),
                "pct": team_record.get("winningPercentage", ""),
                "record": f'{team_record.get("wins", "")}-{team_record.get("losses", "")}',
                "streak": team_record.get("streak", {}).get("streakCode", ""),
                "last_10": team_record.get("records", {}).get("splitRecords", []),
            }

    save_json(teams, OUTPUT_FILE)

    print(f"✅ Saved team context for {len(teams)} teams")
    print(f"📁 {OUTPUT_FILE}")

    return teams


if __name__ == "__main__":
    build_team_context_file()