from pathlib import Path
import numpy as np
import pandas as pd

RAW_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
OUTPUT_FILE = Path("data/processed/hitter_pitch_type_metrics_last_30_days.csv")


def is_barrel(row):
    ev = row.get("launch_speed")
    la = row.get("launch_angle")

    if pd.isna(ev) or pd.isna(la):
        return False

    return ev >= 98 and 26 <= la <= 30


def total_bases(event):
    if event == "single":
        return 1
    if event == "double":
        return 2
    if event == "triple":
        return 3
    if event == "home_run":
        return 4
    return 0


def safe_rate(numerator, denominator, multiplier=1):
    numerator = numerator.fillna(0)
    denominator = denominator.fillna(0)

    return np.where(
        denominator > 0,
        numerator / denominator * multiplier,
        0,
    )


def build_hitter_pitch_type_metrics():
    df = pd.read_csv(RAW_FILE, low_memory=False)

    df = df[df["batter"].notna()]
    df = df[df["pitch_type"].notna()]

    df["is_bip"] = df["type"] == "X"
    df["is_hard_hit"] = df["launch_speed"] >= 95
    df["is_barrel"] = df.apply(is_barrel, axis=1)
    df["total_bases"] = df["events"].apply(total_bases)

    at_bat_events = [
        "single", "double", "triple", "home_run",
        "field_out", "force_out", "grounded_into_double_play",
        "field_error", "strikeout", "strikeout_double_play",
        "fielders_choice", "fielders_choice_out",
        "double_play", "triple_play",
    ]

    df["is_ab"] = df["events"].isin(at_bat_events)
    df["is_hit"] = df["events"].isin(["single", "double", "triple", "home_run"])

    grouped = df.groupby(
        ["batter", "player_name", "pitch_type"],
        dropna=False,
    ).agg(
        Pitches=("pitch_type", "count"),
        BIP=("is_bip", "sum"),
        AB=("is_ab", "sum"),
        H=("is_hit", "sum"),
        TB=("total_bases", "sum"),
        xwOBA=("estimated_woba_using_speedangle", "mean"),
        Barrels=("is_barrel", "sum"),
        HH=("is_hard_hit", "sum"),
        LA=("launch_angle", "mean"),
    ).reset_index()

    grouped["ISO"] = safe_rate(grouped["TB"] - grouped["H"], grouped["AB"])
    grouped["Brl/BIP%"] = safe_rate(grouped["Barrels"], grouped["BIP"], 100)
    grouped["HH%"] = safe_rate(grouped["HH"], grouped["BIP"], 100)

    grouped["PitchTypeScore"] = (
        grouped["ISO"] * 130
        + grouped["xwOBA"].fillna(0) * 80
        + grouped["Brl/BIP%"] * 1.2
        + grouped["HH%"] * 0.45
    ).clip(0, 100)

    final = grouped[[
        "batter",
        "player_name",
        "pitch_type",
        "Pitches",
        "BIP",
        "ISO",
        "xwOBA",
        "Brl/BIP%",
        "HH%",
        "LA",
        "PitchTypeScore",
    ]].copy()

    final = final.replace([np.inf, -np.inf], 0)
    final = final.fillna(0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Saved hitter pitch-type metrics for {final['batter'].nunique()} hitters")
    print(f"📁 {OUTPUT_FILE}")

    return final


if __name__ == "__main__":
    build_hitter_pitch_type_metrics()