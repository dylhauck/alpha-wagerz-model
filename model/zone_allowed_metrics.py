from pathlib import Path
import numpy as np
import pandas as pd

RAW_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
OUTPUT_FILE = Path("data/processed/pitcher_zone_allowed_last_30_days.csv")


def safe_rate(numerator, denominator, multiplier=1):
    numerator = numerator.fillna(0)
    denominator = denominator.fillna(0)

    return np.where(
        denominator > 0,
        numerator / denominator * multiplier,
        0,
    )


def is_barrel(row):
    ev = row.get("launch_speed")
    la = row.get("launch_angle")

    if pd.isna(ev) or pd.isna(la):
        return False

    return ev >= 98 and 26 <= la <= 30


def expected_hr_value(row):
    ev = row.get("launch_speed")
    la = row.get("launch_angle")
    event = row.get("events")

    if event == "home_run":
        return 1.0

    if pd.isna(ev) or pd.isna(la):
        return 0.0

    if ev >= 105 and 20 <= la <= 34:
        return 0.65
    if ev >= 100 and 22 <= la <= 35:
        return 0.45
    if ev >= 98 and 24 <= la <= 32:
        return 0.30
    if ev >= 95 and 20 <= la <= 36:
        return 0.12

    return 0.0


def zone_score(row):
    return max(0, min(100, (
        row.get("xwOBA", 0) * 95
        + row.get("Brl/BIP%", 0) * 1.5
        + row.get("HH%", 0) * 0.5
        + row.get("xHR/Pitch%", 0) * 8
    )))


def zone_label(score):
    if score >= 70:
        return "Hot"
    if score <= 35:
        return "Cold"
    return "Neutral"


def build_zone_allowed_metrics():
    df = pd.read_csv(RAW_FILE, low_memory=False)

    df = df[df["pitcher"].notna()]
    df = df[df["zone"].notna()]

    df["is_bip"] = df["type"] == "X"
    df["is_hard_hit"] = df["launch_speed"] >= 95
    df["is_barrel"] = df.apply(is_barrel, axis=1)
    df["xHR"] = df.apply(expected_hr_value, axis=1)

    grouped = df.groupby(
        ["pitcher", "player_name", "zone"],
        dropna=False,
    ).agg(
        Pitches=("pitch_type", "count"),
        BIP=("is_bip", "sum"),
        xwOBA=("estimated_woba_using_speedangle", "mean"),
        Barrels=("is_barrel", "sum"),
        HH=("is_hard_hit", "sum"),
        xHR=("xHR", "sum"),
    ).reset_index()

    grouped["Brl/BIP%"] = safe_rate(grouped["Barrels"], grouped["BIP"], 100)
    grouped["HH%"] = safe_rate(grouped["HH"], grouped["BIP"], 100)
    grouped["xHR/Pitch%"] = safe_rate(grouped["xHR"], grouped["Pitches"], 100)
    grouped["Zone Score"] = grouped.apply(zone_score, axis=1)
    grouped["Zone Label"] = grouped["Zone Score"].apply(zone_label)

    final = grouped[[
        "pitcher",
        "player_name",
        "zone",
        "Pitches",
        "BIP",
        "xwOBA",
        "Brl/BIP%",
        "HH%",
        "xHR",
        "xHR/Pitch%",
        "Zone Score",
        "Zone Label",
    ]].copy()

    final = final.replace([np.inf, -np.inf], 0).fillna(0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Saved zone allowed metrics for {final['pitcher'].nunique()} pitchers")
    print(f"📁 {OUTPUT_FILE}")

    return final


if __name__ == "__main__":
    build_zone_allowed_metrics()