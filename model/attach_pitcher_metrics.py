import json
from pathlib import Path

import pandas as pd

from model.scores.pitcher_detail import attach_pitcher_detail_scores
from model.scores.pitcher_labels import attach_pitcher_labels
from utils.json_utils import clean_value

GAMES_DIR = Path("data/processed/games")
PITCHER_METRICS_FILE = Path("data/processed/pitcher_metrics_last_30_days.csv")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def normalize_name(name):
    name = str(name or "").strip().lower().replace(".", "")
    name = " ".join(name.split())

    if "," in name:
        last, first = [part.strip() for part in name.split(",", 1)]
        return f"{first} {last}"

    return name.replace(",", "")


def build_lookup():
    df = pd.read_csv(PITCHER_METRICS_FILE)

    df["lookup_name"] = df["player_name"].apply(normalize_name)
    df["lookup_id"] = df["pitcher"].astype(str)

    by_name = {
        row["lookup_name"]: row.to_dict()
        for _, row in df.iterrows()
    }

    by_id = {
        row["lookup_id"]: row.to_dict()
        for _, row in df.iterrows()
    }

    return by_name, by_id


def find_metrics(name, pitcher_id, by_name, by_id):
    if pitcher_id and str(pitcher_id) in by_id:
        return by_id[str(pitcher_id)]

    return by_name.get(normalize_name(name), {})


def format_pitcher(name, team, opponent, by_name, by_id, pitcher_id=None):
    metrics = find_metrics(name, pitcher_id, by_name, by_id)

    pitcher = {
        "Team": team,
        "Pitcher": name,
        "Pitcher ID": clean_value(metrics.get("pitcher", pitcher_id or "")),
        "Throws": clean_value(metrics.get("Throws", "")),
        "Opponent": opponent,

        "HR Risk": clean_value(metrics.get("HR Risk", "")),
        "K Upside": clean_value(metrics.get("K Upside", "")),
        "Pitcher Notes": clean_value(metrics.get("Pitcher Notes", "")),

        "Pitch Score": clean_value(metrics.get("Pitch Score", "")),
        "Strikeout Score": clean_value(metrics.get("Strikeout Score", "")),

        "Pitches": clean_value(metrics.get("Pitches", "")),
        "BF": clean_value(metrics.get("BF", "")),
        "IP": clean_value(metrics.get("IP", "")),

        "HR Vulnerability": clean_value(metrics.get("HR Vulnerability", "")),
        "Fly Ball Profile": clean_value(metrics.get("Fly Ball Profile", "")),
        "Barrel Profile": clean_value(metrics.get("Barrel Profile", "")),

        "xwOBA": clean_value(metrics.get("xwOBA", "")),
        "xwOBAcon": clean_value(metrics.get("xwOBAcon", "")),

        "CSW%": clean_value(metrics.get("CSW%", "")),
        "SwStr%": clean_value(metrics.get("SwStr%", "")),
        "Ball%": clean_value(metrics.get("Ball%", "")),

        "PulledBrl%": clean_value(metrics.get("PulledBrl%", "")),
        "Brl/BIP%": clean_value(metrics.get("Brl/BIP%", "")),
        "FB%": clean_value(metrics.get("FB%", "")),
        "GB%": clean_value(metrics.get("GB%", "")),
        "HH%": clean_value(metrics.get("HH%", "")),

        "K%": clean_value(metrics.get("K%", "")),
        "BB%": clean_value(metrics.get("BB%", "")),
        "HR/9": clean_value(metrics.get("HR/9", "")),

        "AvgEV": clean_value(metrics.get("AvgEV", "")),
        "AvgLA": clean_value(metrics.get("AvgLA", "")),
        "FBv": clean_value(metrics.get("FBv", "")),
    }

    pitcher = attach_pitcher_detail_scores(pitcher)
    pitcher = attach_pitcher_labels(pitcher)

    return pitcher


def attach_pitcher_metrics_to_games():
    by_name, by_id = build_lookup()

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)

        away_sp_id = (
            game.get("away_sp_id")
            or game.get("away_pitcher_id")
            or game.get("away_probable_pitcher_id")
        )

        home_sp_id = (
            game.get("home_sp_id")
            or game.get("home_pitcher_id")
            or game.get("home_probable_pitcher_id")
        )

        game["pitchers"] = [
            format_pitcher(
                game.get("away_sp", ""),
                game.get("away_team", ""),
                game.get("home_team", ""),
                by_name,
                by_id,
                away_sp_id,
            ),
            format_pitcher(
                game.get("home_sp", ""),
                game.get("home_team", ""),
                game.get("away_team", ""),
                by_name,
                by_id,
                home_sp_id,
            ),
        ]

        save_json(game, file)

    print("✅ Attached pitcher metrics to game files")


if __name__ == "__main__":
    attach_pitcher_metrics_to_games()