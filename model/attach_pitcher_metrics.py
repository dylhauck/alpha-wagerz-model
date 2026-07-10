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

PITCHER_COUNT_FIELDS = [
    "Pitches",
    "BF",
    "BIP",
    "HR",
    "K",
    "BB",
]

PITCHER_AVERAGE_FIELDS = [
    "xwOBA",
    "xwOBAcon",
    "AvgEV",
    "AvgLA",
    "FBv",
]

PITCHER_SCORE_FIELDS = [
    "Pitch Score",
    "Strikeout Score",
    "HR Vulnerability",
]

def find_one_pitcher_metrics(name, pitcher_id, by_name, by_id):
    if pitcher_id and str(pitcher_id) in by_id:
        return by_id[str(pitcher_id)]

    normalized = normalize_name(name)

    if normalized in by_name:
        return by_name[normalized]

    return {}


def metric_value(metrics, field):
    if not metrics:
        return ""

    value = metrics.get(field, "")

    if value not in ["", None] and not pd.isna(value):
        return value

    aliases = {
        "xwOBA": ["Pitcher xwOBA"],
        "xwOBAcon": ["Pitcher xwOBAcon"],
    }

    for alias in aliases.get(field, []):
        value = metrics.get(alias, "")

        if value not in ["", None] and not pd.isna(value):
            return value

    return ""

def blend_average_field(sources, field):
    weighted_total = 0.0
    weight_total = 0.0

    for metrics, weight in sources:
        value = metric_value(metrics, field)

        if value in ["", None]:
            continue

        try:
            numeric = float(value)
        except Exception:
            continue

        weighted_total += numeric * weight
        weight_total += weight

    if weight_total == 0:
        return ""

    return weighted_total / weight_total


def blend_count_field(sources, field):
    weighted_total = 0.0
    found_value = False

    for metrics, weight in sources:
        value = metric_value(metrics, field)

        if value in ["", None]:
            continue

        try:
            numeric = float(value)
        except Exception:
            continue

        weighted_total += numeric * weight
        found_value = True

    if not found_value:
        return ""

    return round(weighted_total)


def blend_pitcher_metrics(last_30, season, longterm):
    sources = [
        (last_30 or {}, 0.40),
        (season or {}, 0.35),
        (longterm or {}, 0.25),
    ]

    blended = {}

    for field in PITCHER_COUNT_FIELDS:
        blended[field] = blend_count_field(sources, field)

    for field in PITCHER_AVERAGE_FIELDS:
        blended[field] = blend_average_field(sources, field)

    for field in PITCHER_SCORE_FIELDS:
        blended[field] = blend_average_field(sources, field)

    weighted_bip = 0.0
    weighted_pitches = 0.0
    weighted_bf = 0.0
    weighted_ip = 0.0

    weighted_fb = 0.0
    weighted_gb = 0.0
    weighted_hh = 0.0
    weighted_barrels = 0.0
    weighted_pulled_barrels = 0.0

    weighted_csw = 0.0
    weighted_swstr = 0.0
    weighted_balls = 0.0

    weighted_k = 0.0
    weighted_bb = 0.0
    weighted_hr = 0.0

    for metrics, weight in sources:
        source_bip = f(metric_value(metrics, "BIP"), 0)
        source_pitches = f(metric_value(metrics, "Pitches"), 0)
        source_bf = f(metric_value(metrics, "BF"), 0)
        source_ip = f(metric_value(metrics, "IP"), 0)
        source_hr = f(metric_value(metrics, "HR"), 0)
        source_k = f(metric_value(metrics, "K"), 0)
        source_bb = f(metric_value(metrics, "BB"), 0)

        weighted_bip += source_bip * weight
        weighted_pitches += source_pitches * weight
        weighted_bf += source_bf * weight
        weighted_ip += source_ip * weight

        weighted_hr += source_hr * weight
        weighted_k += source_k * weight
        weighted_bb += source_bb * weight

        if source_bip > 0:
            source_fb_rate = f(metric_value(metrics, "FB%"), 0) / 100
            source_gb_rate = f(metric_value(metrics, "GB%"), 0) / 100
            source_hh_rate = f(metric_value(metrics, "HH%"), 0) / 100
            source_barrel_rate = f(metric_value(metrics, "Brl/BIP%"), 0) / 100
            source_pulled_barrel_rate = (
                f(metric_value(metrics, "PulledBrl%"), 0) / 100
            )

            weighted_fb += source_bip * source_fb_rate * weight
            weighted_gb += source_bip * source_gb_rate * weight
            weighted_hh += source_bip * source_hh_rate * weight
            weighted_barrels += source_bip * source_barrel_rate * weight
            weighted_pulled_barrels += (
                source_bip * source_pulled_barrel_rate * weight
            )

        if source_pitches > 0:
            source_csw_rate = f(metric_value(metrics, "CSW%"), 0) / 100
            source_swstr_rate = f(metric_value(metrics, "SwStr%"), 0) / 100
            source_ball_rate = f(metric_value(metrics, "Ball%"), 0) / 100

            weighted_csw += source_pitches * source_csw_rate * weight
            weighted_swstr += source_pitches * source_swstr_rate * weight
            weighted_balls += source_pitches * source_ball_rate * weight

    blended["Pitches"] = round(weighted_pitches) if weighted_pitches else ""
    blended["BF"] = round(weighted_bf) if weighted_bf else ""
    blended["BIP"] = round(weighted_bip) if weighted_bip else ""
    blended["HR"] = round(weighted_hr) if weighted_hr else 0
    blended["K"] = round(weighted_k) if weighted_k else 0
    blended["BB"] = round(weighted_bb) if weighted_bb else 0

    if weighted_bip > 0:
        blended["FB%"] = round(weighted_fb / weighted_bip * 100, 2)
        blended["GB%"] = round(weighted_gb / weighted_bip * 100, 2)
        blended["HH%"] = round(weighted_hh / weighted_bip * 100, 2)
        blended["Brl/BIP%"] = round(
            weighted_barrels / weighted_bip * 100,
            2,
        )
        blended["PulledBrl%"] = round(
            weighted_pulled_barrels / weighted_bip * 100,
            2,
        )
    else:
        blended["FB%"] = ""
        blended["GB%"] = ""
        blended["HH%"] = ""
        blended["Brl/BIP%"] = ""
        blended["PulledBrl%"] = ""

    if weighted_pitches > 0:
        blended["CSW%"] = round(
            weighted_csw / weighted_pitches * 100,
            2,
        )
        blended["SwStr%"] = round(
            weighted_swstr / weighted_pitches * 100,
            2,
        )
        blended["Ball%"] = round(
            weighted_balls / weighted_pitches * 100,
            2,
        )
    else:
        blended["CSW%"] = ""
        blended["SwStr%"] = ""
        blended["Ball%"] = ""

    if weighted_bf > 0:
        blended["K%"] = round(weighted_k / weighted_bf * 100, 2)
        blended["BB%"] = round(weighted_bb / weighted_bf * 100, 2)
    else:
        blended["K%"] = ""
        blended["BB%"] = ""

    blended["IP"] = round(weighted_ip, 1) if weighted_ip else ""

    if weighted_ip > 0:
        blended["HR/9"] = round(weighted_hr / weighted_ip * 9, 2)
    else:
        blended["HR/9"] = ""

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


def lineup_avg(opponent_hitters, field, default=50):
    values = []

    for hitter in opponent_hitters or []:
        value = f(hitter.get(field), None)
        if value is not None:
            values.append(value)

    return sum(values) / len(values) if values else default


def build_opponent_profile(opponent_hitters):
    return {
        "Opponent Matchup Score": lineup_avg(opponent_hitters, "Matchup", 50),
        "Opponent K Score": lineup_avg(opponent_hitters, "kHR", 50),
        "Opponent SwStr%": lineup_avg(opponent_hitters, "SwStr%", 10),
        "Opponent ISO": lineup_avg(opponent_hitters, "ISO", 0.150),
        "Opponent xwOBA": lineup_avg(opponent_hitters, "xwOBA", 0.315),
        "Opponent xwOBAcon": lineup_avg(opponent_hitters, "xwOBAcon", 0.360),
        "Opponent Brl/BIP%": lineup_avg(opponent_hitters, "Brl/BIP%", 8),
        "Opponent PulledBrl%": lineup_avg(opponent_hitters, "PulledBrl%", 4),
        "Opponent FB%": lineup_avg(opponent_hitters, "FB%", 27),
        "Opponent HH%": lineup_avg(opponent_hitters, "HH%", 39),
        "Opponent LA": lineup_avg(opponent_hitters, "LA", 16),
    }


def apply_pitcher_matchup_adjustment(pitcher, opponent_hitters):
    opponent = build_opponent_profile(opponent_hitters)

    for key, value in opponent.items():
        pitcher[key] = round(value, 3)

    matchup = opponent["Opponent Matchup Score"]
    opponent_k = opponent["Opponent K Score"]
    opponent_swstr = opponent["Opponent SwStr%"]

    pitcher["Matchup Score"] = round(
        clamp(
            matchup * 0.45
            + opponent_k * 0.35
            + opponent_swstr * 2.0
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