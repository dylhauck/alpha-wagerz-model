import json
from pathlib import Path
import pandas as pd

from model.scores.alpha import alpha_score


GAMES_DIR = Path("data/processed/games")
HITTER_METRICS_FILE = Path("data/processed/hitter_metrics_last_30_days.csv")


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def normalize_name(name):
    return str(name).strip().lower().replace(".", "")


def build_metrics_lookup():
    df = pd.read_csv(HITTER_METRICS_FILE)
    df["lookup_name"] = df["player_name"].apply(normalize_name)

    return {
        row["lookup_name"]: row.to_dict()
        for _, row in df.iterrows()
    }


def format_hitter(name, metrics_lookup, game):
    key = normalize_name(name)
    metrics = metrics_lookup.get(key, {})

    hitter = {
        "Player": name,
        "Matchup": "",
        "Test Score": "",
        "Ceiling": "",
        "Zone Fit": "",
        "HR Form": "",
        "kHR": "",
        "Pitches": metrics.get("Pitches", ""),
        "BIP": metrics.get("BIP", ""),
        "ISO": metrics.get("ISO", ""),
        "xwOBA": metrics.get("xwOBA", ""),
        "xwOBAcon": metrics.get("xwOBAcon", ""),
        "SwStr%": metrics.get("SwStr%", ""),
        "PulledBrl%": metrics.get("PulledBrl%", ""),
        "Brl/BIP%": metrics.get("Brl/BIP%", ""),
        "Sweet Spot%": metrics.get("Sweet Spot%", ""),
        "FB%": metrics.get("FB%", ""),
        "HH%": metrics.get("HH%", ""),
        "LA": metrics.get("LA", ""),
    }

    # Build Alpha Wagerz score breakdown
    scores = alpha_score(hitter, game=game)

    hitter["Power"] = scores["Power"]
    hitter["Contact"] = scores["Contact"]
    hitter["Pitcher"] = scores["Pitcher"]
    hitter["Weather"] = scores["Weather"]
    hitter["Park"] = scores["Park"]
    hitter["Recent"] = scores["Recent"]
    hitter["Likely"] = scores["Likely"]

    return hitter


def attach_hitter_metrics_to_games():
    metrics_lookup = build_metrics_lookup()

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)

        away_names = game.get("away_hitters", [])
        home_names = game.get("home_hitters", [])

        game["hitters"] = {
            "away": [format_hitter(name, metrics_lookup, game) for name in away_names],
            "home": [format_hitter(name, metrics_lookup, game) for name in home_names],
        }

        save_json(game, file)

    print("✅ Attached hitter metrics and Likely scores to game files")


if __name__ == "__main__":
    attach_hitter_metrics_to_games()