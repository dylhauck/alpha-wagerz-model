from pathlib import Path
import numpy as np
import pandas as pd

RAW_LAST_30_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
RAW_SEASON_FILE = Path("data/raw/statcast/statcast_season.csv")
RAW_LONGTERM_FILE = Path("data/raw/statcast/statcast_longterm.csv")
PLAYER_REFERENCE_FILE = Path("data/reference/player_reference.csv")

OUTPUT_LAST_30_FILE = Path("data/processed/hitter_metrics_last_30_days.csv")
OUTPUT_SEASON_FILE = Path("data/processed/hitter_metrics_season.csv")
OUTPUT_LONGTERM_FILE = Path("data/processed/hitter_metrics_longterm.csv")


def load_player_reference():
    if not PLAYER_REFERENCE_FILE.exists():
        return {}

    ref = pd.read_csv(PLAYER_REFERENCE_FILE)
    if "player_id" not in ref.columns or "player_name" not in ref.columns:
        return {}

    ref["player_id"] = ref["player_id"].astype(str)

    return {
        str(row["player_id"]): row["player_name"]
        for _, row in ref.iterrows()
    }


def clean_statcast_name(value):
    name = str(value or "").strip()
    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        if len(parts) == 2:
            return f"{parts[1]} {parts[0]}".strip()
    return name


def total_bases(event):
    return {
        "single": 1,
        "double": 2,
        "triple": 3,
        "home_run": 4,
    }.get(event, 0)


def safe_rate(numerator, denominator, multiplier=1):
    numerator = numerator.fillna(0)
    denominator = denominator.fillna(0)

    return np.where(
        denominator > 0,
        numerator / denominator * multiplier,
        0,
    )


def is_barrel(row):
    """
    Statcast-style barrel approximation.
    The old EV >= 98 and LA 26-30 rule was too strict and undercounted barrels.
    """
    ev = row.get("launch_speed")
    la = row.get("launch_angle")

    if pd.isna(ev) or pd.isna(la):
        return False

    ev = float(ev)
    la = float(la)

    if ev < 98:
        return False

    expand = ev - 98
    lower = max(8, 26 - (expand * 1.5))
    upper = min(50, 30 + (expand * 1.5))

    return lower <= la <= upper


def spray_angle(row):
    hc_x = row.get("hc_x")
    hc_y = row.get("hc_y")

    if pd.isna(hc_x) or pd.isna(hc_y):
        return None

    return np.degrees(np.arctan2(float(hc_x) - 125.42, 198.27 - float(hc_y)))


def is_pulled(row):
    angle = spray_angle(row)
    stand = str(row.get("stand", "")).upper()

    if angle is None:
        return False

    if stand == "R":
        return angle < -10

    if stand == "L":
        return angle > 10

    return False


def build_metrics_from_file(raw_file, output_file, label):
    if not raw_file.exists():
        print(f"⚠️ Missing {raw_file}. Skipping {label} hitter metrics.")
        return pd.DataFrame()

    player_lookup = load_player_reference()
    df = pd.read_csv(raw_file, low_memory=False)

    if df.empty or "batter" not in df.columns:
        print(f"⚠️ No usable batter data in {raw_file}. Skipping {label}.")
        return pd.DataFrame()

    df = df[df["batter"].notna()].copy()
    df["batter"] = df["batter"].astype(int).astype(str)

    df["player_name_from_ref"] = df["batter"].map(player_lookup).fillna("")

    if "player_name" in df.columns:
        df["player_name_from_csv"] = df["player_name"].apply(clean_statcast_name)
    else:
        df["player_name_from_csv"] = ""

    df["player_name"] = np.where(
        df["player_name_from_ref"] != "",
        df["player_name_from_ref"],
        df["player_name_from_csv"],
    )

    df = df[df["player_name"].astype(str).str.strip() != ""].copy()

    required_defaults = {
        "type": "",
        "description": "",
        "launch_speed": np.nan,
        "launch_angle": np.nan,
        "bb_type": "",
        "events": "",
        "estimated_woba_using_speedangle": np.nan,
        "pitch_type": "",
        "hc_x": np.nan,
        "hc_y": np.nan,
        "stand": "",
    }

    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    df["is_bip"] = df["type"] == "X"
    df["is_swinging_strike"] = df["description"].str.contains("swinging_strike", na=False)
    df["is_hard_hit"] = df["launch_speed"] >= 95
    df["is_sweet_spot"] = df["launch_angle"].between(8, 32)
    df["is_fly_ball"] = df["bb_type"].isin(["fly_ball", "popup"])
    df["is_barrel"] = df.apply(is_barrel, axis=1)
    df["is_pulled"] = df.apply(is_pulled, axis=1)
    df["is_pulled_barrel"] = df["is_barrel"] & df["is_pulled"]
    df["total_bases"] = df["events"].apply(total_bases)

    df["xwoba_contact_value"] = np.where(
        df["is_bip"],
        df["estimated_woba_using_speedangle"],
        np.nan,
    )

    event_woba = {
        "walk": 0.69,
        "hit_by_pitch": 0.72,
        "single": 0.88,
        "double": 1.25,
        "triple": 1.58,
        "home_run": 2.03,
        "strikeout": 0.00,
        "field_out": 0.00,
        "force_out": 0.00,
        "grounded_into_double_play": 0.00,
        "double_play": 0.00,
        "fielders_choice": 0.00,
        "fielders_choice_out": 0.00,
    }

    df["estimated_xwoba_value"] = df["estimated_woba_using_speedangle"]
    df["event_woba_value"] = df["events"].map(event_woba)
    df["xwoba_value"] = df["estimated_xwoba_value"].where(
        df["estimated_xwoba_value"].notna(),
        df["event_woba_value"],
    )

    at_bat_events = [
        "single", "double", "triple", "home_run",
        "field_out", "force_out", "grounded_into_double_play",
        "field_error", "strikeout", "strikeout_double_play",
        "fielders_choice", "fielders_choice_out",
        "double_play", "triple_play",
    ]

    plate_appearance_events = at_bat_events + [
        "walk", "hit_by_pitch", "sac_fly", "sac_bunt",
    ]

    df["is_ab"] = df["events"].isin(at_bat_events)
    df["is_pa_event"] = df["events"].isin(plate_appearance_events)
    df["is_hit"] = df["events"].isin(["single", "double", "triple", "home_run"])

    grouped = df.groupby(["batter", "player_name"], dropna=False).agg(
        Pitches=("pitch_type", "count"),
        BIP=("is_bip", "sum"),
        PA=("is_pa_event", "sum"),
        AB=("is_ab", "sum"),
        H=("is_hit", "sum"),
        TB=("total_bases", "sum"),
        xwOBA=("xwoba_value", "mean"),
        xwOBAcon=("xwoba_contact_value", "mean"),
        SwStr=("is_swinging_strike", "sum"),
        PulledBrl=("is_pulled_barrel", "sum"),
        Barrels=("is_barrel", "sum"),
        SweetSpot=("is_sweet_spot", "sum"),
        FB=("is_fly_ball", "sum"),
        HH=("is_hard_hit", "sum"),
        LA=("launch_angle", "mean"),
    ).reset_index()

    grouped["ISO"] = safe_rate(grouped["TB"] - grouped["H"], grouped["AB"])
    grouped["SwStr%"] = safe_rate(grouped["SwStr"], grouped["Pitches"], 100)
    grouped["PulledBrl%"] = safe_rate(grouped["PulledBrl"], grouped["BIP"], 100)
    grouped["Brl/BIP%"] = safe_rate(grouped["Barrels"], grouped["BIP"], 100)
    grouped["Sweet Spot%"] = safe_rate(grouped["SweetSpot"], grouped["BIP"], 100)
    grouped["FB%"] = safe_rate(grouped["FB"], grouped["BIP"], 100)
    grouped["HH%"] = safe_rate(grouped["HH"], grouped["BIP"], 100)

    final = grouped[[
        "batter",
        "player_name",
        "Pitches",
        "BIP",
        "PA",
        "AB",
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
    ]].copy()

    final = final.replace([np.inf, -np.inf], 0).fillna(0)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(output_file, index=False)

    print(f"✅ Saved {label} hitter metrics for {len(final)} players")
    print(f"📁 {output_file}")

    return final


def build_hitter_metrics():
    last_30 = build_metrics_from_file(
        RAW_LAST_30_FILE,
        OUTPUT_LAST_30_FILE,
        "last-30-day",
    )

    season = build_metrics_from_file(
        RAW_SEASON_FILE,
        OUTPUT_SEASON_FILE,
        "season",
    )

    if RAW_LONGTERM_FILE.exists():
        longterm = build_metrics_from_file(
            RAW_LONGTERM_FILE,
            OUTPUT_LONGTERM_FILE,
            "longterm",
        )
    elif RAW_SEASON_FILE.exists():
        print("⚠️ Missing raw longterm Statcast file. Using season as longterm baseline for now.")
        longterm = build_metrics_from_file(
            RAW_SEASON_FILE,
            OUTPUT_LONGTERM_FILE,
            "longterm-season-fallback",
        )
    else:
        longterm = pd.DataFrame()
        print("⚠️ Missing both longterm and season raw files. Longterm metrics not created.")

    return last_30, season, longterm


if __name__ == "__main__":
    build_hitter_metrics()
