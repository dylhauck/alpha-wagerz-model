from pathlib import Path
import pandas as pd

from utils.json_utils import load_json, save_json

GAMES_DIR = Path("data/processed/games")
PITCH_MIX_FILE = Path("data/processed/pitch_mix_last_30_days.csv")
HITTER_PT_FILE = Path("data/processed/hitter_pitch_type_metrics_last_30_days.csv")

def load_pitch_mix():
    if not PITCH_MIX_FILE.exists():
        print(f"⚠️ Missing {PITCH_MIX_FILE}")
        return {}

    df = pd.read_csv(PITCH_MIX_FILE)

    lookup = {}

    for pitcher_id, group in df.groupby("pitcher"):
        lookup[str(int(pitcher_id))] = group.to_dict("records")

    return lookup


def load_hitter_pitch_type():
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


def get_pitcher_id_from_name(game, pitcher_obj):
    # Temporary fallback: pitcher metrics currently do not always carry MLB ID.
    # If Pitcher ID exists later, this becomes automatic.
    return pitcher_obj.get("Pitcher ID") or pitcher_obj.get("pitcher") or pitcher_obj.get("id")


def opposing_pitcher(game, side):
    pitchers = game.get("pitchers", [])

    if side == "away":
        opponent_team = game.get("home_team", "")
    else:
        opponent_team = game.get("away_team", "")

    for pitcher in pitchers:
        if pitcher.get("Team") == opponent_team:
            return pitcher

    return None


def score_pitch_type_matchup(hitter_id, pitcher_id, pitch_mix_lookup, hitter_pt_lookup):
    if not hitter_id or not pitcher_id:
        return {
            "Pitch Type Score": 50,
            "Pitch Type Notes": "Missing hitter or pitcher ID",
            "Pitch Type Matchups": [],
        }

    pitch_mix = pitch_mix_lookup.get(str(pitcher_id), [])

    if not pitch_mix:
        return {
            "Pitch Type Score": 50,
            "Pitch Type Notes": "Pitch mix unavailable",
            "Pitch Type Matchups": [],
        }

    weighted_score = 0
    total_usage = 0
    matchups = []

    for pitch in pitch_mix:
        pitch_type = pitch.get("pitch_type")
        usage = float(pitch.get("Usage%", 0) or 0)

        hitter_row = hitter_pt_lookup.get((str(hitter_id), pitch_type))

        if not hitter_row:
            continue

        score = float(hitter_row.get("PitchTypeScore", 0) or 0)

        weighted_score += score * usage
        total_usage += usage

        matchups.append({
            "pitch_type": pitch_type,
            "usage": round(usage, 1),
            "hitter_score": round(score, 1),
        })

    if total_usage <= 0:
        return {
            "Pitch Type Score": 50,
            "Pitch Type Notes": "No matching hitter pitch-type data",
            "Pitch Type Matchups": [],
        }

    final_score = round(weighted_score / total_usage, 1)

    matchups.sort(key=lambda x: x["usage"], reverse=True)

    top_notes = [
        f'{m["pitch_type"]} {m["usage"]}% / hitter {m["hitter_score"]}'
        for m in matchups[:3]
    ]

    return {
        "Pitch Type Score": final_score,
        "Pitch Type Notes": "; ".join(top_notes),
        "Pitch Type Matchups": matchups,
    }


def attach_pitch_type_matchups():
    pitch_mix_lookup = load_pitch_mix()
    hitter_pt_lookup = load_hitter_pitch_type()

    updated = 0

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)

        hitters_obj = game.get("hitters", {})
        if not isinstance(hitters_obj, dict):
                hitters_obj = {
                "away": [],
                "home": [],
                }
                game["hitters"] = hitters_obj

        for side in ["away", "home"]:
            pitcher = opposing_pitcher(game, side)
            pitcher_id = get_pitcher_id_from_name(game, pitcher or {})

            for hitter in hitters_obj.get(side, []):

                hitter_id = hitter.get("Player ID")

                result = score_pitch_type_matchup(
                    hitter_id,
                    pitcher_id,
                    pitch_mix_lookup,
                    hitter_pt_lookup,
                )

                hitter["Pitch Type Score"] = result["Pitch Type Score"]
                hitter["Pitch Type Notes"] = result["Pitch Type Notes"]
                hitter["Pitch Type Matchups"] = result["Pitch Type Matchups"]

        save_json(game, file)
        updated += 1

    print(f"✅ Attached pitch-type matchups to {updated} game files")


if __name__ == "__main__":
    attach_pitch_type_matchups()