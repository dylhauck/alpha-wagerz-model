from pathlib import Path
import pandas as pd

from utils.json_utils import load_json, save_json, clean_value

GAMES_DIR = Path("data/processed/games")
BULLPEN_FILE = Path("data/processed/bullpen_metrics_last_30_days.csv")


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


def load_bullpen_lookup():
    if not BULLPEN_FILE.exists():
        print(f"⚠️ Missing {BULLPEN_FILE}")
        return {}

    df = pd.read_csv(BULLPEN_FILE)

    return {
        str(row["pitching_team"]): row.to_dict()
        for _, row in df.iterrows()
    }


def attach_bullpen_context():
    lookup = load_bullpen_lookup()
    updated = 0

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})
        if not game:
            continue

        for side in ["away", "home"]:
            opponent_team = game.get("home_team") if side == "away" else game.get("away_team")
            opponent_abbr = TEAM_NAME_TO_ABBR.get(opponent_team, "")
            bullpen = lookup.get(opponent_abbr, {})

            hitters = game.get("hitters", {})

            if isinstance(hitters, list):
                hitters = {
                    "away": game.get("away_hitters", []),
                    "home": game.get("home_hitters", []),
             }

        for hitter in hitters.get(side, []):
                hitter["Bullpen"] = clean_value(bullpen.get("Bullpen Score", ""))
                hitter["Bullpen xwOBA"] = clean_value(bullpen.get("xwOBA", ""))
                hitter["Bullpen HR/Pitch%"] = clean_value(bullpen.get("HR/Pitch%", ""))
                hitter["Bullpen Brl/BIP%"] = clean_value(bullpen.get("Brl/BIP%", ""))
                hitter["Bullpen HH%"] = clean_value(bullpen.get("HH%", ""))
                hitter["Bullpen SwStr%"] = clean_value(bullpen.get("SwStr%", ""))

        save_json(game, file)
        updated += 1

    print(f"✅ Attached bullpen context to {updated} game files")


if __name__ == "__main__":
    attach_bullpen_context()