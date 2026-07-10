from pathlib import Path
import pandas as pd

from utils.json_utils import load_json, save_json, clean_value

GAMES_DIR = Path("data/processed/games")
TEAM_OFFENSE_FILE = Path("data/processed/team_offense_last_30_days.csv")


TEAM_NAME_TO_ABBR = {
    "Arizona Diamondbacks": "ARI",
    "Athletics": "OAK",
    "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL",
    "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN",
    "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL",
    "Detroit Tigers": "DET",
    "Houston Astros": "HOU",
    "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA",
    "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA",
    "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN",
    "New York Mets": "NYM",
    "New York Yankees": "NYY",
    "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD",
    "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA",
    "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR",
    "Washington Nationals": "WAS",
}


def load_team_lookup():
    if not TEAM_OFFENSE_FILE.exists():
        print(f"⚠️ Missing {TEAM_OFFENSE_FILE}")
        return {}

    df = pd.read_csv(TEAM_OFFENSE_FILE)

    return {
        str(row["batting_team"]): row.to_dict()
        for _, row in df.iterrows()
    }


def attach_team_context():
    lookup = load_team_lookup()
    updated = 0

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})
        if not game:
            continue

        for side in ["away", "home"]:
            team_name = game.get("away_team") if side == "away" else game.get("home_team")
            abbr = TEAM_NAME_TO_ABBR.get(team_name, "")
            team_metrics = lookup.get(abbr, {})

            hitters = game.get("hitters", {})

            if isinstance(hitters, list):
                hitters = {
                "away": game.get("away_hitters", []),
                "home": game.get("home_hitters", []),
    }

            for hitter in hitters.get(side, []):
                hitter["Team Offense"] = clean_value(
                    team_metrics.get("Team Offense Score", "")
                )
                hitter["Team ISO"] = clean_value(team_metrics.get("ISO", ""))
                hitter["Team xwOBA"] = clean_value(team_metrics.get("xwOBA", ""))
                hitter["Team HR%"] = clean_value(team_metrics.get("HR%", ""))
                hitter["Team Brl/BIP%"] = clean_value(team_metrics.get("Brl/BIP%", ""))
                hitter["Team HH%"] = clean_value(team_metrics.get("HH%", ""))

        save_json(game, file)
        updated += 1

    print(f"✅ Attached team context to {updated} game files")


if __name__ == "__main__":
    attach_team_context()