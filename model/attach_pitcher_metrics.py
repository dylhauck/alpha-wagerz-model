import json
from pathlib import Path
import pandas as pd

GAMES_DIR = Path("data/processed/games")
PITCHER_METRICS_FILE = Path("data/processed/pitcher_metrics_last_30_days.csv")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def normalize_name(name):
    return str(name).strip().lower().replace(".", "")


def build_lookup():
    df = pd.read_csv(PITCHER_METRICS_FILE)
    df["lookup_name"] = df["player_name"].apply(normalize_name)

    return {
        row["lookup_name"]: row.to_dict()
        for _, row in df.iterrows()
    }


def format_pitcher(name, team, opponent, lookup):
    metrics = lookup.get(normalize_name(name), {})

    return {
        "Team": team,
        "Pitcher": name,
        "Throws": "",
        "Opponent": opponent,
        "Pitch Score": metrics.get("Pitch Score", ""),
        "Strikeout Score": metrics.get("Strikeout Score", ""),
        "xwOBA": metrics.get("xwOBA", ""),
        "CSW%": metrics.get("CSW%", ""),
        "SwStr%": metrics.get("SwStr%", ""),
        "Ball%": metrics.get("Ball%", ""),
        "PulledBrl%": metrics.get("PulledBrl%", ""),
        "Brl/BIP%": metrics.get("Brl/BIP%", ""),
        "FB%": metrics.get("FB%", ""),
        "HH%": metrics.get("HH%", ""),
    }


def attach_pitcher_metrics_to_games():
    lookup = build_lookup()

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)

        game["pitchers"] = [
            format_pitcher(
                game.get("away_sp", ""),
                game.get("away_team", ""),
                game.get("home_team", ""),
                lookup,
            ),
            format_pitcher(
                game.get("home_sp", ""),
                game.get("home_team", ""),
                game.get("away_team", ""),
                lookup,
            ),
        ]

        save_json(game, file)

    print("✅ Attached pitcher metrics to game files")


if __name__ == "__main__":
    attach_pitcher_metrics_to_games()