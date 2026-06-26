from pathlib import Path
import numpy as np
import pandas as pd

RAW_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
OUTPUT_FILE = Path("data/processed/team_offense_last_30_days.csv")


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


def get_batting_team(row):
    topbot = str(row.get("inning_topbot", "")).lower()

    if topbot == "top":
        return row.get("away_team", "")

    if topbot == "bot":
        return row.get("home_team", "")

    return ""


def build_team_offense_metrics():
    df = pd.read_csv(RAW_FILE, low_memory=False)

    df["batting_team"] = df.apply(get_batting_team, axis=1)

    df["is_bip"] = df["type"] == "X"
    df["is_hard_hit"] = df["launch_speed"] >= 95
    df["is_barrel"] = df.apply(is_barrel, axis=1)
    df["is_hr"] = df["events"] == "home_run"
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

    grouped = df.groupby("batting_team", dropna=False).agg(
        Pitches=("pitch_type", "count"),
        BIP=("is_bip", "sum"),
        AB=("is_ab", "sum"),
        H=("is_hit", "sum"),
        TB=("total_bases", "sum"),
        HR=("is_hr", "sum"),
        xwOBA=("estimated_woba_using_speedangle", "mean"),
        Barrels=("is_barrel", "sum"),
        HH=("is_hard_hit", "sum"),
    ).reset_index()

    grouped["ISO"] = safe_rate(grouped["TB"] - grouped["H"], grouped["AB"])
    grouped["HR%"] = safe_rate(grouped["HR"], grouped["AB"], 100)
    grouped["Brl/BIP%"] = safe_rate(grouped["Barrels"], grouped["BIP"], 100)
    grouped["HH%"] = safe_rate(grouped["HH"], grouped["BIP"], 100)

    grouped["Team Offense Score"] = (
        grouped["ISO"] * 120
        + grouped["xwOBA"].fillna(0) * 85
        + grouped["HR%"] * 3.5
        + grouped["Brl/BIP%"] * 1.2
        + grouped["HH%"] * 0.45
    ).clip(0, 100)

    final = grouped[[
        "batting_team",
        "Pitches",
        "AB",
        "HR",
        "ISO",
        "xwOBA",
        "HR%",
        "Brl/BIP%",
        "HH%",
        "Team Offense Score",
    ]].copy()

    final = final[final["batting_team"] != ""]
    final = final.replace([np.inf, -np.inf], 0)
    final = final.fillna(0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Saved team offense metrics for {len(final)} teams")
    print(f"📁 {OUTPUT_FILE}")

    return final


if __name__ == "__main__":
    build_team_offense_metrics()