from pathlib import Path
import pandas as pd

from model.scores.alpha import alpha_score
from utils.json_utils import load_json, save_json, clean_value
from model.scores.hitter_detail import attach_hitter_detail_scores

GAMES_DIR = Path("data/processed/games")
HITTER_METRICS_FILE = Path("data/processed/hitter_metrics_last_30_days.csv")


def normalize_name(name):
    return str(name).strip().lower().replace(".", "").replace(",", "")


def hitter_name(hitter):
    if isinstance(hitter, dict):
        return hitter.get("name", "") or hitter.get("Player", "")
    return str(hitter)


def hitter_id(hitter):
    if isinstance(hitter, dict):
        return hitter.get("id") or hitter.get("Player ID")
    return None


def get_existing_value(hitter_input, key, default=""):
    if isinstance(hitter_input, dict):
        return hitter_input.get(key, default)
    return default


def build_metrics_lookup():
    df = pd.read_csv(HITTER_METRICS_FILE)

    df["lookup_name"] = df["player_name"].apply(normalize_name)
    df["lookup_id"] = df["batter"].astype(str)

    by_name = {row["lookup_name"]: row.to_dict() for _, row in df.iterrows()}
    by_id = {row["lookup_id"]: row.to_dict() for _, row in df.iterrows()}

    return by_name, by_id


def find_metrics(hitter, by_name, by_id):
    mlb_id = hitter_id(hitter)

    if mlb_id and str(mlb_id) in by_id:
        return by_id[str(mlb_id)]

    key = normalize_name(hitter_name(hitter))

    if key in by_name:
        return by_name[key]

    parts = key.split()
    if len(parts) >= 2:
        reversed_key = normalize_name(f"{parts[-1]} {' '.join(parts[:-1])}")
        return by_name.get(reversed_key, {})

    return {}


def get_opposing_pitcher(game, side):
    pitchers = game.get("pitchers", [])

    opponent_team = game.get("home_team", "") if side == "away" else game.get("away_team", "")

    return next(
        (pitcher for pitcher in pitchers if pitcher.get("Team") == opponent_team),
        None,
    )


def format_hitter(hitter_input, by_name, by_id, game, side):
    name = hitter_name(hitter_input)
    metrics = find_metrics(hitter_input, by_name, by_id)
    opposing_pitcher = get_opposing_pitcher(game, side)

    hitter = {
        "Player": name,
        "Player ID": hitter_id(hitter_input),

        "Team Offense": clean_value(get_existing_value(hitter_input, "Team Offense")),
        "Team ISO": clean_value(get_existing_value(hitter_input, "Team ISO")),
        "Team xwOBA": clean_value(get_existing_value(hitter_input, "Team xwOBA")),
        "Team HR%": clean_value(get_existing_value(hitter_input, "Team HR%")),
        "Team Brl/BIP%": clean_value(get_existing_value(hitter_input, "Team Brl/BIP%")),
        "Team HH%": clean_value(get_existing_value(hitter_input, "Team HH%")),

        "Bullpen": clean_value(get_existing_value(hitter_input, "Bullpen")),
        "Bullpen xwOBA": clean_value(get_existing_value(hitter_input, "Bullpen xwOBA")),
        "Bullpen HR/Pitch%": clean_value(get_existing_value(hitter_input, "Bullpen HR/Pitch%")),
        "Bullpen Brl/BIP%": clean_value(get_existing_value(hitter_input, "Bullpen Brl/BIP%")),
        "Bullpen HH%": clean_value(get_existing_value(hitter_input, "Bullpen HH%")),
        "Bullpen SwStr%": clean_value(get_existing_value(hitter_input, "Bullpen SwStr%")),

        "Pitch Type Score": clean_value(get_existing_value(hitter_input, "Pitch Type Score")),
        "Pitch Type Notes": clean_value(get_existing_value(hitter_input, "Pitch Type Notes")),
        "Pitch Type Matchups": get_existing_value(hitter_input, "Pitch Type Matchups", []),
        "Arsenal Score": clean_value(get_existing_value(hitter_input, "Arsenal Score")),

        "Fastball Matchup": clean_value(get_existing_value(hitter_input, "Fastball Matchup")),
        "Breaking Ball Matchup": clean_value(get_existing_value(hitter_input, "Breaking Ball Matchup")),
        "Offspeed Matchup": clean_value(get_existing_value(hitter_input, "Offspeed Matchup")),
        "xHR Matchup": clean_value(get_existing_value(hitter_input, "xHR Matchup")),
        "Pitch Arsenal Notes": clean_value(get_existing_value(hitter_input, "Pitch Arsenal Notes")),
        "Hot Zones Allowed": clean_value(get_existing_value(hitter_input, "Hot Zones Allowed")),
        "Cold Zones Allowed": clean_value(get_existing_value(hitter_input, "Cold Zones Allowed")),

        "Matchup": "",
        "Test Score": "",
        "Ceiling": "",
        "Zone Fit": "",
        "HR Form": "",
        "kHR": "",

        "Pitches": clean_value(metrics.get("Pitches", "")),
        "BIP": clean_value(metrics.get("BIP", "")),
        "ISO": clean_value(metrics.get("ISO", "")),
        "xwOBA": clean_value(metrics.get("xwOBA", "")),
        "xwOBAcon": clean_value(metrics.get("xwOBAcon", "")),
        "SwStr%": clean_value(metrics.get("SwStr%", "")),
        "PulledBrl%": clean_value(metrics.get("PulledBrl%", "")),
        "Brl/BIP%": clean_value(metrics.get("Brl/BIP%", "")),
        "Sweet Spot%": clean_value(metrics.get("Sweet Spot%", "")),
        "FB%": clean_value(metrics.get("FB%", "")),
        "HH%": clean_value(metrics.get("HH%", "")),
        "LA": clean_value(metrics.get("LA", "")),
    }

    scores = alpha_score(hitter, pitcher=opposing_pitcher, game=game)

    hitter["Power"] = clean_value(scores.get("Power", ""))
    hitter["Contact"] = clean_value(scores.get("Contact", ""))
    hitter["Pitcher"] = clean_value(scores.get("Pitcher", ""))
    hitter["Pitch Type"] = clean_value(scores.get("Pitch Type", ""))
    hitter["Arsenal Score"] = clean_value(hitter.get("Arsenal Score", ""))
    hitter["Fastball Matchup"] = clean_value(hitter.get("Fastball Matchup", ""))
    hitter["Breaking Ball Matchup"] = clean_value(hitter.get("Breaking Ball Matchup", ""))
    hitter["Offspeed Matchup"] = clean_value(hitter.get("Offspeed Matchup", ""))
    hitter["xHR Matchup"] = clean_value(hitter.get("xHR Matchup", ""))
    hitter["Pitch Arsenal Notes"] = clean_value(hitter.get("Pitch Arsenal Notes", ""))
    hitter["Hot Zones Allowed"] = clean_value(hitter.get("Hot Zones Allowed", ""))
    hitter["Cold Zones Allowed"] = clean_value(hitter.get("Cold Zones Allowed", ""))
    hitter["Team"] = clean_value(scores.get("Team", ""))
    hitter["Bullpen"] = clean_value(scores.get("Bullpen", ""))
    hitter["Weather"] = clean_value(scores.get("Weather", ""))
    hitter["Park"] = clean_value(scores.get("Park", ""))
    hitter["Recent"] = clean_value(scores.get("Recent", ""))
    hitter["Likely"] = clean_value(scores.get("Likely", ""))
    hitter["Confidence"] = clean_value(scores.get("Confidence", ""))
    hitter["Reasons"] = scores.get("Reasons", [])
    hitter = attach_hitter_detail_scores(hitter)

    return hitter


def attach_hitter_metrics_to_games():
    by_name, by_id = build_metrics_lookup()

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})

        if not game:
            continue

        away_hitters = game.get("away_hitters", [])
        home_hitters = game.get("home_hitters", [])

        game["hitters"] = {
            "away": [
                format_hitter(hitter, by_name, by_id, game, "away")
                for hitter in away_hitters
            ],
            "home": [
                format_hitter(hitter, by_name, by_id, game, "home")
                for hitter in home_hitters
            ],
        }

        save_json(game, file)

    print("✅ Attached hitter metrics using MLB IDs/full names")


if __name__ == "__main__":
    attach_hitter_metrics_to_games()