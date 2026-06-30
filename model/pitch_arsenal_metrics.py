from pathlib import Path
import numpy as np
import pandas as pd

RAW_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
OUTPUT_FILE = Path("data/processed/pitch_arsenal_last_30_days.csv")


PITCH_FAMILY = {
    "FF": "Fastball",
    "FA": "Fastball",
    "SI": "Fastball",
    "FC": "Fastball",
    "SL": "Slider",
    "ST": "Slider",
    "CU": "Curve",
    "KC": "Curve",
    "CH": "Changeup",
    "FS": "Splitter",
    "FO": "Splitter",
    "SV": "Breaking",
}


def safe_rate(numerator, denominator, multiplier=1):
    numerator = numerator.fillna(0)
    denominator = denominator.fillna(0)

    return np.where(
        denominator > 0,
        numerator / denominator * multiplier,
        0,
    )


def pitch_family(pitch_type):
    return PITCH_FAMILY.get(str(pitch_type), "Other")


def is_barrel(row):
    ev = row.get("launch_speed")
    la = row.get("launch_angle")

    if pd.isna(ev) or pd.isna(la):
        return False

    return ev >= 98 and 26 <= la <= 30


def expected_hr_value(row):
    ev = row.get("launch_speed")
    la = row.get("launch_angle")
    distance = row.get("hit_distance_sc")
    event = row.get("events")

    if event == "home_run":
        return 1.0

    if pd.isna(ev) or pd.isna(la):
        return 0.0

    score = 0.0

    if ev >= 105 and 20 <= la <= 34:
        score = 0.65
    elif ev >= 100 and 22 <= la <= 35:
        score = 0.45
    elif ev >= 98 and 24 <= la <= 32:
        score = 0.30
    elif ev >= 95 and 20 <= la <= 36:
        score = 0.12

    if not pd.isna(distance) and distance >= 390:
        score += 0.15
    elif not pd.isna(distance) and distance >= 375:
        score += 0.08

    return min(score, 1.0)


def grade_pitch(row):
    xwoba = row.get("xwOBA", 0)
    brl = row.get("Brl/BIP%", 0)
    hh = row.get("HH%", 0)
    xhr = row.get("xHR/Pitch%", 0)
    swstr = row.get("SwStr%", 0)

    # Higher = worse for pitcher / better for hitters
    return max(0, min(100, (
        xwoba * 90
        + brl * 1.5
        + hh * 0.45
        + xhr * 8
        - swstr * 0.45
    )))


def build_pitch_arsenal_metrics():
    df = pd.read_csv(RAW_FILE, low_memory=False)

    df = df[df["pitcher"].notna()]
    df = df[df["pitch_type"].notna()]

    df["pitch_family"] = df["pitch_type"].apply(pitch_family)
    df["stand"] = df["stand"].fillna("")
    df["is_bip"] = df["type"] == "X"
    df["is_hard_hit"] = df["launch_speed"] >= 95
    df["is_barrel"] = df.apply(is_barrel, axis=1)
    df["is_swinging_strike"] = df["description"].str.contains("swinging_strike", na=False)
    df["xHR"] = df.apply(expected_hr_value, axis=1)

    grouped = df.groupby(
        ["pitcher", "player_name", "stand", "pitch_type", "pitch_family"],
        dropna=False,
    ).agg(
        Pitches=("pitch_type", "count"),
        BIP=("is_bip", "sum"),
        AvgVelo=("release_speed", "mean"),
        AvgSpin=("release_spin_rate", "mean"),
        AvgIVB=("pfx_z", "mean"),
        AvgHB=("pfx_x", "mean"),
        xwOBA=("estimated_woba_using_speedangle", "mean"),
        Barrels=("is_barrel", "sum"),
        HH=("is_hard_hit", "sum"),
        SwStr=("is_swinging_strike", "sum"),
        xHR=("xHR", "sum"),
    ).reset_index()

    totals = grouped.groupby(["pitcher", "stand"])["Pitches"].sum().reset_index()
    totals = totals.rename(columns={"Pitches": "TotalPitches"})

    grouped = grouped.merge(totals, on=["pitcher", "stand"], how="left")

    grouped["Usage%"] = safe_rate(grouped["Pitches"], grouped["TotalPitches"], 100)
    grouped["Brl/BIP%"] = safe_rate(grouped["Barrels"], grouped["BIP"], 100)
    grouped["HH%"] = safe_rate(grouped["HH"], grouped["BIP"], 100)
    grouped["SwStr%"] = safe_rate(grouped["SwStr"], grouped["Pitches"], 100)
    grouped["xHR/Pitch%"] = safe_rate(grouped["xHR"], grouped["Pitches"], 100)

    grouped["Pitch Arsenal Grade"] = grouped.apply(grade_pitch, axis=1)

    final = grouped[[
        "pitcher",
        "player_name",
        "stand",
        "pitch_type",
        "pitch_family",
        "Pitches",
        "TotalPitches",
        "Usage%",
        "AvgVelo",
        "AvgSpin",
        "AvgIVB",
        "AvgHB",
        "xwOBA",
        "Brl/BIP%",
        "HH%",
        "SwStr%",
        "xHR",
        "xHR/Pitch%",
        "Pitch Arsenal Grade",
    ]].copy()

    final = final.replace([np.inf, -np.inf], 0).fillna(0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Saved pitch arsenal metrics for {final['pitcher'].nunique()} pitchers")
    print(f"📁 {OUTPUT_FILE}")

    return final


if __name__ == "__main__":
    build_pitch_arsenal_metrics()