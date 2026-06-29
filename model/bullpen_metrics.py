from pathlib import Path
import numpy as np
import pandas as pd

RAW_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
OUTPUT_FILE = Path("data/processed/bullpen_metrics_last_30_days.csv")


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


def pitching_team(row):
    topbot = str(row.get("inning_topbot", "")).lower()

    if topbot == "top":
        return row.get("home_team", "")

    if topbot == "bot":
        return row.get("away_team", "")

    return ""


def build_bullpen_metrics():
    df = pd.read_csv(RAW_FILE, low_memory=False)

    df["pitching_team"] = df.apply(pitching_team, axis=1)

    # Basic bullpen approximation:
    # innings 6+ are more likely bullpen appearances.
    df = df[df["inning"] >= 6]

    df["is_bip"] = df["type"] == "X"
    df["is_hr"] = df["events"] == "home_run"
    df["is_hard_hit"] = df["launch_speed"] >= 95
    df["is_barrel"] = df.apply(is_barrel, axis=1)
    df["is_swinging_strike"] = df["description"].str.contains("swinging_strike", na=False)

    grouped = df.groupby("pitching_team", dropna=False).agg(
        Pitches=("pitch_type", "count"),
        BIP=("is_bip", "sum"),
        HR=("is_hr", "sum"),
        xwOBA=("estimated_woba_using_speedangle", "mean"),
        Barrels=("is_barrel", "sum"),
        HH=("is_hard_hit", "sum"),
        SwStr=("is_swinging_strike", "sum"),
    ).reset_index()

    grouped["HR/Pitch%"] = safe_rate(grouped["HR"], grouped["Pitches"], 100)
    grouped["Brl/BIP%"] = safe_rate(grouped["Barrels"], grouped["BIP"], 100)
    grouped["HH%"] = safe_rate(grouped["HH"], grouped["BIP"], 100)
    grouped["SwStr%"] = safe_rate(grouped["SwStr"], grouped["Pitches"], 100)

    # Higher = more vulnerable bullpen for hitters
    grouped["Bullpen Score"] = (
        grouped["xwOBA"].fillna(0) * 90
        + grouped["HR/Pitch%"] * 8
        + grouped["Brl/BIP%"] * 1.4
        + grouped["HH%"] * 0.55
        - grouped["SwStr%"] * 0.5
    ).clip(0, 100)

    final = grouped[[
        "pitching_team",
        "Pitches",
        "BIP",
        "HR",
        "xwOBA",
        "HR/Pitch%",
        "Brl/BIP%",
        "HH%",
        "SwStr%",
        "Bullpen Score",
    ]].copy()

    final = final[final["pitching_team"] != ""]
    final = final.replace([np.inf, -np.inf], 0).fillna(0)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Saved bullpen metrics for {len(final)} teams")
    print(f"📁 {OUTPUT_FILE}")

    return final


if __name__ == "__main__":
    build_bullpen_metrics()