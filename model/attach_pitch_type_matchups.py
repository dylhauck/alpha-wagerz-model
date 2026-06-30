from pathlib import Path
import pandas as pd

from utils.json_utils import load_json, save_json, clean_value

GAMES_DIR = Path("data/processed/games")
ARSENAL_FILE = Path("data/processed/pitch_arsenal_last_30_days.csv")
HITTER_PT_FILE = Path("data/processed/hitter_pitch_type_metrics_last_30_days.csv")
ZONE_FILE = Path("data/processed/pitcher_zone_allowed_last_30_days.csv")


def safe_float(value, default=0):
    try:
        if value == "" or value is None:
            return default
        return float(value)
    except Exception:
        return default


def load_arsenal_lookup():
    if not ARSENAL_FILE.exists():
        print(f"⚠️ Missing {ARSENAL_FILE}")
        return {}

    df = pd.read_csv(ARSENAL_FILE)

    lookup = {}

    for pitcher_id, group in df.groupby("pitcher"):
        lookup[str(int(pitcher_id))] = group.to_dict("records")

    return lookup


def load_hitter_pitch_type_lookup():
    if not HITTER_PT_FILE.exists():
        print(f"⚠️ Missing {HITTER_PT_FILE}")
        return {}

    df = pd.read_csv(HITTER_PT_FILE)

    lookup = {}

    for _, row in df.iterrows():
        hitter_id = str(int(row["batter"]))
        pitch_type = row["pitch_type"]
        lookup[(hitter_id, pitch_type)] = row.to_dict()

    return lookup


def load_zone_lookup():
    if not ZONE_FILE.exists():
        print(f"⚠️ Missing {ZONE_FILE}")
        return {}

    df = pd.read_csv(ZONE_FILE)

    lookup = {}

    for pitcher_id, group in df.groupby("pitcher"):
        zones = group.sort_values("Zone Score", ascending=False).to_dict("records")
        lookup[str(int(pitcher_id))] = zones

    return lookup


def opposing_pitcher(game, side):
    pitchers = game.get("pitchers", [])

    opponent_team = game.get("home_team", "") if side == "away" else game.get("away_team", "")

    for pitcher in pitchers:
        if pitcher.get("Team") == opponent_team:
            return pitcher

    return None


def get_pitcher_id(pitcher):
    if not pitcher:
        return None

    return (
        pitcher.get("Pitcher ID")
        or pitcher.get("pitcher")
        or pitcher.get("id")
    )


def get_hitter_id(hitter):
    return hitter.get("Player ID") or hitter.get("id")


def get_hitter_stand(hitter):
    return hitter.get("Bats") or hitter.get("stand") or ""


def family_bucket(pitch_family):
    if pitch_family in ["Fastball"]:
        return "Fastball"
    if pitch_family in ["Slider", "Curve", "Breaking"]:
        return "Breaking"
    if pitch_family in ["Changeup", "Splitter"]:
        return "Offspeed"
    return "Other"


def score_hitter_vs_arsenal(hitter, pitcher_id, arsenal_lookup, hitter_pt_lookup, zone_lookup):
    hitter_id = get_hitter_id(hitter)
    hitter_stand = str(get_hitter_stand(hitter)).upper()

    if not hitter_id or not pitcher_id:
        return {
            "Pitch Type Score": 50,
            "Arsenal Score": 50,
            "Fastball Matchup": "",
            "Breaking Ball Matchup": "",
            "Offspeed Matchup": "",
            "xHR Matchup": "",
            "Pitch Arsenal Notes": "Missing hitter or pitcher ID",
            "Hot Zones Allowed": "",
            "Cold Zones Allowed": "",
            "Pitch Type Matchups": [],
        }

    all_arsenal = arsenal_lookup.get(str(pitcher_id), [])

    if not all_arsenal:
        return {
            "Pitch Type Score": 50,
            "Arsenal Score": 50,
            "Fastball Matchup": "",
            "Breaking Ball Matchup": "",
            "Offspeed Matchup": "",
            "xHR Matchup": "",
            "Pitch Arsenal Notes": "Pitch arsenal unavailable",
            "Hot Zones Allowed": "",
            "Cold Zones Allowed": "",
            "Pitch Type Matchups": [],
        }

    handed_arsenal = [
        row for row in all_arsenal
        if str(row.get("stand", "")).upper() == hitter_stand
    ]

    arsenal = handed_arsenal if handed_arsenal else all_arsenal

    weighted_score = 0
    total_usage = 0
    weighted_xhr = 0

    family_scores = {
        "Fastball": {"score": 0, "usage": 0},
        "Breaking": {"score": 0, "usage": 0},
        "Offspeed": {"score": 0, "usage": 0},
    }

    matchups = []

    for pitch in arsenal:
        pitch_type = pitch.get("pitch_type")
        pitch_family = pitch.get("pitch_family")
        bucket = family_bucket(pitch_family)

        usage = safe_float(pitch.get("Usage%"))
        pitcher_grade = safe_float(pitch.get("Pitch Arsenal Grade"), 50)
        pitcher_xhr = safe_float(pitch.get("xHR/Pitch%"))

        hitter_row = hitter_pt_lookup.get((str(hitter_id), pitch_type))
        hitter_score = safe_float(hitter_row.get("PitchTypeScore", 50), 50) if hitter_row else 50

        matchup_score = (
            hitter_score * 0.55
            + pitcher_grade * 0.35
            + pitcher_xhr * 10
        )

        weighted_score += matchup_score * usage
        weighted_xhr += pitcher_xhr * usage
        total_usage += usage

        if bucket in family_scores:
            family_scores[bucket]["score"] += matchup_score * usage
            family_scores[bucket]["usage"] += usage

        matchups.append({
            "pitch_type": pitch_type,
            "pitch_family": pitch_family,
            "usage": round(usage, 1),
            "hitter_score": round(hitter_score, 1),
            "pitcher_grade": round(pitcher_grade, 1),
            "xHR/Pitch%": round(pitcher_xhr, 2),
            "matchup_score": round(matchup_score, 1),
        })

    if total_usage <= 0:
        final_score = 50
        xhr_matchup = 0
    else:
        final_score = round(weighted_score / total_usage, 1)
        xhr_matchup = round(weighted_xhr / total_usage, 2)

    def family_result(name):
        usage = family_scores[name]["usage"]
        if usage <= 0:
            return ""
        return round(family_scores[name]["score"] / usage, 1)

    zones = zone_lookup.get(str(pitcher_id), [])
    hot_zones = [
        str(int(z["zone"])) for z in zones
        if z.get("Zone Label") == "Hot"
    ][:3]
    cold_zones = [
        str(int(z["zone"])) for z in zones
        if z.get("Zone Label") == "Cold"
    ][:3]

    matchups.sort(key=lambda x: x["usage"], reverse=True)

    notes = []
    for item in matchups[:3]:
        notes.append(
            f'{item["pitch_type"]} {item["usage"]}% / score {item["matchup_score"]}'
        )

    return {
        "Pitch Type Score": final_score,
        "Arsenal Score": final_score,
        "Fastball Matchup": family_result("Fastball"),
        "Breaking Ball Matchup": family_result("Breaking"),
        "Offspeed Matchup": family_result("Offspeed"),
        "xHR Matchup": xhr_matchup,
        "Pitch Arsenal Notes": "; ".join(notes),
        "Hot Zones Allowed": ", ".join(hot_zones),
        "Cold Zones Allowed": ", ".join(cold_zones),
        "Pitch Type Matchups": matchups,
    }


def attach_pitch_type_matchups():
    arsenal_lookup = load_arsenal_lookup()
    hitter_pt_lookup = load_hitter_pitch_type_lookup()
    zone_lookup = load_zone_lookup()

    updated = 0

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file, default={})
        if not game:
            continue

        hitters_obj = game.get("hitters", {})

        if not isinstance(hitters_obj, dict):
            hitters_obj = {"away": [], "home": []}
            game["hitters"] = hitters_obj

        for side in ["away", "home"]:
            pitcher = opposing_pitcher(game, side)
            pitcher_id = get_pitcher_id(pitcher)

            for hitter in hitters_obj.get(side, []):
                result = score_hitter_vs_arsenal(
                    hitter,
                    pitcher_id,
                    arsenal_lookup,
                    hitter_pt_lookup,
                    zone_lookup,
                )

                hitter["Pitch Type Score"] = clean_value(result["Pitch Type Score"])
                hitter["Arsenal Score"] = clean_value(result["Arsenal Score"])
                hitter["Fastball Matchup"] = clean_value(result["Fastball Matchup"])
                hitter["Breaking Ball Matchup"] = clean_value(result["Breaking Ball Matchup"])
                hitter["Offspeed Matchup"] = clean_value(result["Offspeed Matchup"])
                hitter["xHR Matchup"] = clean_value(result["xHR Matchup"])
                hitter["Pitch Arsenal Notes"] = clean_value(result["Pitch Arsenal Notes"])
                hitter["Pitch Type Notes"] = clean_value(result["Pitch Arsenal Notes"])
                hitter["Hot Zones Allowed"] = clean_value(result["Hot Zones Allowed"])
                hitter["Cold Zones Allowed"] = clean_value(result["Cold Zones Allowed"])
                hitter["Pitch Type Matchups"] = result["Pitch Type Matchups"]

        save_json(game, file)
        updated += 1

    print(f"✅ Attached pitch arsenal matchups to {updated} game files")


if __name__ == "__main__":
    attach_pitch_type_matchups()