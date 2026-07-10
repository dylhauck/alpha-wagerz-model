import json
from pathlib import Path

import pandas as pd

from model.scores.pitcher_detail import attach_pitcher_detail_scores
from model.scores.pitcher_labels import attach_pitcher_labels
from utils.json_utils import clean_value

GAMES_DIR = Path("data/processed/games")
PITCHER_METRICS_FILE = Path("data/processed/pitcher_metrics_last_30_days.csv")
PITCHER_SEASON_METRICS_FILE = Path("data/processed/pitcher_metrics_season.csv")
PITCHER_LONGTERM_METRICS_FILE = Path("data/processed/pitcher_metrics_longterm.csv")

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

def build_lookup_from_file(filepath):
    if not filepath.exists():
        return {}, {}

    df = pd.read_csv(filepath)

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

def build_lookup():
    last_30_by_name, last_30_by_id = build_lookup_from_file(PITCHER_METRICS_FILE)
    season_by_name, season_by_id = build_lookup_from_file(PITCHER_SEASON_METRICS_FILE)
    longterm_by_name, longterm_by_id = build_lookup_from_file(PITCHER_LONGTERM_METRICS_FILE)

    return {
        "last_30_by_name": last_30_by_name,
        "last_30_by_id": last_30_by_id,
        "season_by_name": season_by_name,
        "season_by_id": season_by_id,
        "longterm_by_name": longterm_by_name,
        "longterm_by_id": longterm_by_id,
    }

PITCHER_BLEND_FIELDS = [
    "Pitches", "BF", "IP", "HR", "K", "BB",
    "Pitcher xwOBA", "xwOBAcon", "CSW%", "SwStr%", "Ball%",
    "PulledBrl%", "Brl/BIP%", "FB%", "GB%", "HH%",
    "K%", "BB%", "HR/9", "AvgEV", "AvgLA", "FBv",
    "Pitch Score", "Strikeout Score", "HR Vulnerability",
]


def find_one_pitcher_metrics(name, pitcher_id, by_name, by_id):
    if pitcher_id and str(pitcher_id) in by_id:
        return by_id[str(pitcher_id)]

    normalized = normalize_name(name)

    if normalized in by_name:
        return by_name[normalized]

    return {}


def blend_pitcher_metrics(last_30, season, longterm):
    sources = [
        (last_30 or {}, 0.40),
        (season or {}, 0.35),
        (longterm or {}, 0.25),
    ]

    blended = {}

    for field in PITCHER_BLEND_FIELDS:
        total = 0
        weight_total = 0

        for metrics, weight in sources:
            value = metrics.get(field, "")
            if value not in ["", None]:
                try:
                    total += float(value) * weight
                    weight_total += weight
                except Exception:
                    pass

        blended[field] = total / weight_total if weight_total else ""

    for source in [last_30, season, longterm]:
        if source:
            blended["pitcher"] = source.get("pitcher", "")
            blended["player_name"] = source.get("player_name", "")
            break

    return blended


def find_metrics(name, pitcher_id, lookup):
    last_30 = find_one_pitcher_metrics(name, pitcher_id, lookup["last_30_by_name"], lookup["last_30_by_id"])
    season = find_one_pitcher_metrics(name, pitcher_id, lookup["season_by_name"], lookup["season_by_id"])
    longterm = find_one_pitcher_metrics(name, pitcher_id, lookup["longterm_by_name"], lookup["longterm_by_id"])

    metrics = blend_pitcher_metrics(last_30, season, longterm)

    if last_30 and season and longterm:
        metrics["Metric Source"] = "Blended"
    elif longterm:
        metrics["Metric Source"] = "Longterm"
    elif season:
        metrics["Metric Source"] = "Season"
    elif last_30:
        metrics["Metric Source"] = "Last 30"
    else:
        metrics["Metric Source"] = "Missing"

    return metrics

def f(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def matchup_k_score(opponent_hitters):
    if not opponent_hitters:
        return 50

    scores = []

    for hitter in opponent_hitters:
        swstr = f(hitter.get("SwStr%"), 10)
        khr = f(hitter.get("kHR"), 50)
        matchup = f(hitter.get("Matchup"), 50)

        score = (
            swstr * 3.0
            + khr * 0.45
            + matchup * 0.25
        )

        scores.append(score)

    return clamp(sum(scores) / len(scores), 20, 90)


def apply_pitcher_matchup_adjustment(pitcher, opponent_hitters):
    matchup = matchup_k_score(opponent_hitters)

    base_pitch_score = f(pitcher.get("Pitch Score"), 50)
    base_k_score = f(pitcher.get("Strikeout Score"), 50)

    pitcher["Matchup Score"] = round(matchup, 1)

    pitcher["Pitch Score"] = round(
        clamp(
            base_pitch_score * 0.65
            + matchup * 0.35
        ),
        1,
    )

    pitcher["Strikeout Score"] = round(
        clamp(
            base_k_score * 0.55
            + matchup * 0.45
        ),
        1,
    )

    return pitcher

def format_pitcher(name, team, opponent, lookup, pitcher_id=None, opponent_hitters=None):
    metrics = find_metrics(name, pitcher_id, lookup)

    pitcher = {
        "Team": team,
        "Pitcher": name,
        "Pitcher ID": clean_value(metrics.get("pitcher", pitcher_id or "")),
        "Metric Source": clean_value(metrics.get("Metric Source", "")),
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

        "Pitcher xwOBA": clean_value(metrics.get("Pitcher xwOBA", "")),
        "Pitcher xwOBAcon": clean_value(metrics.get("Pitcher xwOBAcon", "")),

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

    pitcher = apply_pitcher_matchup_adjustment(pitcher, opponent_hitters or [])
    pitcher = attach_pitcher_detail_scores(pitcher)
    pitcher = attach_pitcher_labels(pitcher)

    return pitcher


def attach_pitcher_metrics_to_games():
    lookup = build_lookup()

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
                lookup,
                away_sp_id,
                game.get("home_hitters", []),
            ),
            format_pitcher(
                game.get("home_sp", ""),
                game.get("home_team", ""),
                game.get("away_team", ""),
                lookup,
                home_sp_id,
                game.get("away_hitters", []),
            ),
        ]

        save_json(game, file)

    print("✅ Attached pitcher metrics to game files")


if __name__ == "__main__":
    attach_pitcher_metrics_to_games()