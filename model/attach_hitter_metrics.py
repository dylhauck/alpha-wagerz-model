from pathlib import Path
import pandas as pd

from model.scores.alpha import alpha_score
from utils.json_utils import load_json, save_json, clean_value
from model.scores.slate_normalizer import normalize_slate_hitters

GAMES_DIR = Path("data/processed/games")

HITTER_METRICS_FILE = Path("data/processed/hitter_metrics_last_30_days.csv")
HITTER_SEASON_METRICS_FILE = Path("data/processed/hitter_metrics_season.csv")
HITTER_LONGTERM_METRICS_FILE = Path("data/processed/hitter_metrics_longterm.csv")

METRIC_FIELDS = [
    "Pitches",
    "BIP",
    "ISO",
    "xwOBA",
    "xwOBAcon",
    "SwStr%",
    "PulledBrl%",
    "Brl/BIP%",
    "Sweet Spot%",
    "FB%",
    "HH%",
    "LA",
]


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


def build_lookup_from_file(filepath):
    if not filepath.exists():
        return {}, {}

    df = pd.read_csv(filepath)

    df["lookup_name"] = df["player_name"].apply(normalize_name)
    df["lookup_id"] = df["batter"].astype(str)

    by_name = {row["lookup_name"]: row.to_dict() for _, row in df.iterrows()}
    by_id = {row["lookup_id"]: row.to_dict() for _, row in df.iterrows()}

    return by_name, by_id


def build_metrics_lookup():
    last_30_by_name, last_30_by_id = build_lookup_from_file(HITTER_METRICS_FILE)
    season_by_name, season_by_id = build_lookup_from_file(HITTER_SEASON_METRICS_FILE)
    longterm_by_name, longterm_by_id = build_lookup_from_file(HITTER_LONGTERM_METRICS_FILE)

    return {
        "last_30_by_name": last_30_by_name,
        "last_30_by_id": last_30_by_id,
        "season_by_name": season_by_name,
        "season_by_id": season_by_id,
        "longterm_by_name": longterm_by_name,
        "longterm_by_id": longterm_by_id,
    }


def find_one_metrics(hitter, by_name, by_id):
    mlb_id = hitter_id(hitter)

    if mlb_id and str(mlb_id) in by_id:
        return by_id[str(mlb_id)]

    key = normalize_name(hitter_name(hitter))

    if key in by_name:
        return by_name[key]

    parts = key.split()
    if len(parts) >= 2:
        reversed_key = normalize_name(f"{parts[-1]} {' '.join(parts[:-1])}")
        if reversed_key in by_name:
            return by_name[reversed_key]

    return {}


def blend_metrics(last_30, season, longterm):
    sources = [
        (last_30 or {}, 0.40),
        (season or {}, 0.35),
        (longterm or {}, 0.25),
    ]

    blended = {}

    for field in METRIC_FIELDS:
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
        if field in ["Pitches", "BIP", "PA", "AB"]:
            blended[field] = round(blended[field]) if blended[field] != "" else ""

    for source in [last_30, season, longterm]:
        if source:
            blended["batter"] = source.get("batter", "")
            blended["player_name"] = source.get("player_name", "")
            break

    return blended


def find_metrics_bundle(hitter, lookup):
    last_30 = find_one_metrics(hitter, lookup["last_30_by_name"], lookup["last_30_by_id"])
    season = find_one_metrics(hitter, lookup["season_by_name"], lookup["season_by_id"])
    longterm = find_one_metrics(hitter, lookup["longterm_by_name"], lookup["longterm_by_id"])

    base = blend_metrics(last_30, season, longterm)

    if last_30 and season and longterm:
        source = "Blended"
    elif longterm:
        source = "Longterm"
    elif season:
        source = "Season"
    elif last_30:
        source = "Last 30"
    else:
        source = "Missing"

    return base or {}, last_30 or {}, season or {}, longterm or {}, source


def metric_value(field, base_metrics):
    value = base_metrics.get(field, "")

    if value is None or value == "":
        return 0

    return clean_value(value)


def recent_metric_value(field, recent_metrics):
    value = recent_metrics.get(field, "")

    if value is None or value == "":
        return ""

    return clean_value(value)


def get_opposing_pitcher(game, side):
    pitchers = game.get("pitchers", [])
    opponent_team = game.get("home_team", "") if side == "away" else game.get("away_team", "")

    return next(
        (pitcher for pitcher in pitchers if pitcher.get("Team") == opponent_team),
        None,
    )


def format_hitter(hitter_input, lookup, game, side):
    name = hitter_name(hitter_input)

    (
        base_metrics,
        last_30_metrics,
        season_metrics,
        longterm_metrics,
        metric_source,
    ) = find_metrics_bundle(hitter_input, lookup)

    opposing_pitcher = get_opposing_pitcher(game, side)

    hitter = {
        "Player": name,
        "Player ID": hitter_id(hitter_input),
        "Metric Source": clean_value(metric_source),

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
    }

    # Main baseline metrics shown on the website.
    for field in METRIC_FIELDS:
        hitter[field] = metric_value(field, base_metrics)

    # Recent metrics used only by score_recent_form().
    for field in METRIC_FIELDS:
        hitter[f"Recent {field}"] = recent_metric_value(field, last_30_metrics)

    # Optional debug/source fields.
    hitter["Recent Metric Source"] = "Last 30" if last_30_metrics else "Missing"
    hitter["Season Metric Source"] = "Season" if season_metrics else "Missing"
    hitter["Longterm Metric Source"] = "Longterm" if longterm_metrics else "Missing"

    scores = alpha_score(hitter, pitcher=opposing_pitcher, game=game)

    hitter["Power"] = clean_value(scores.get("Power", ""))
    hitter["Contact"] = clean_value(scores.get("Contact", ""))
    hitter["Pitcher"] = clean_value(scores.get("Pitcher", ""))
    hitter["Pitch Type"] = clean_value(scores.get("Pitch Type", ""))
    hitter["Team"] = clean_value(scores.get("Team", ""))
    hitter["Bullpen"] = clean_value(scores.get("Bullpen", ""))
    hitter["Weather"] = clean_value(scores.get("Weather", ""))
    hitter["Park"] = clean_value(scores.get("Park", ""))
    hitter["Recent"] = clean_value(scores.get("Recent", ""))
    hitter["Likely"] = clean_value(scores.get("Likely", ""))
    hitter["Confidence"] = clean_value(scores.get("Confidence", ""))
    hitter["Reasons"] = scores.get("Reasons", [])

    hitter["Matchup"] = clean_value(scores.get("Matchup", ""))
    hitter["Test Score"] = clean_value(scores.get("Test Score", ""))
    hitter["Ceiling"] = clean_value(scores.get("Ceiling", ""))
    hitter["Zone Fit"] = clean_value(scores.get("Zone Fit", ""))
    hitter["HR Form"] = clean_value(scores.get("HR Form", ""))
    hitter["kHR"] = clean_value(scores.get("kHR", ""))

    return hitter


def attach_hitter_metrics_to_games():
    lookup = build_metrics_lookup()
    missing = []

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})

        if not game:
            continue

        away_hitters = game.get("away_hitters", [])
        home_hitters = game.get("home_hitters", [])

        game["hitters"] = {
            "away": [
                format_hitter(hitter, lookup, game, "away")
                for hitter in away_hitters
            ],
            "home": [
                format_hitter(hitter, lookup, game, "home")
                for hitter in home_hitters
            ],
        }

        for side in ["away", "home"]:
            for hitter in game["hitters"][side]:
                if hitter.get("Metric Source") == "Missing":
                    missing.append(f"{game.get('game', file.name)}: {hitter.get('Player')}")

        save_json(game, file)

        games_to_save = []

        for file in GAMES_DIR.glob("*.json"):
            game = load_json(file, default={})
        if game:
            games_to_save.append((file, game))

        if games_to_save:
            normalized_games = normalize_slate_hitters([game for _, game in games_to_save])
        else:
            return

    for (file, _), game in zip(games_to_save, normalized_games):
        save_json(game, file)

    print("✅ Attached hitter metrics using longterm baseline + last-30 recent form")

    if missing:
        print(f"⚠️ Hitters with no metrics found: {len(missing)}")
        for item in missing[:30]:
            print(f" - {item}")


if __name__ == "__main__":
    attach_hitter_metrics_to_games()