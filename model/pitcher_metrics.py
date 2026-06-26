from pathlib import Path
import pandas as pd

RAW_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
OUTPUT_FILE = Path("data/processed/pitcher_metrics_last_30_days.csv")


def is_barrel(row):
    ev = row.get("launch_speed")
    la = row.get("launch_angle")

    if pd.isna(ev) or pd.isna(la):
        return False

    return ev >= 98 and 26 <= la <= 30


def build_pitcher_metrics():
    df = pd.read_csv(RAW_FILE, low_memory=False)

    df["is_bip"] = df["type"] == "X"
    df["is_swinging_strike"] = df["description"].str.contains("swinging_strike", na=False)
    df["is_called_strike"] = df["description"].str.contains("called_strike", na=False)
    df["is_ball"] = df["description"].str.contains("ball", na=False)
    df["is_hard_hit"] = df["launch_speed"] >= 95
    df["is_fly_ball"] = df["bb_type"].isin(["fly_ball", "popup"])
    df["is_barrel"] = df.apply(is_barrel, axis=1)

    grouped = df.groupby(["pitcher", "player_name"], dropna=False).agg(
        Pitches=("pitch_type", "count"),
        BIP=("is_bip", "sum"),
        xwOBA=("estimated_woba_using_speedangle", "mean"),
        CSW=("is_called_strike", "sum"),
        SwStr=("is_swinging_strike", "sum"),
        Ball=("is_ball", "sum"),
        PulledBrl=("is_barrel", "sum"),
        Barrels=("is_barrel", "sum"),
        FB=("is_fly_ball", "sum"),
        HH=("is_hard_hit", "sum"),
    ).reset_index()

    grouped["CSW%"] = ((grouped["CSW"] + grouped["SwStr"]) / grouped["Pitches"] * 100).fillna(0)
    grouped["SwStr%"] = (grouped["SwStr"] / grouped["Pitches"] * 100).fillna(0)
    grouped["Ball%"] = (grouped["Ball"] / grouped["Pitches"] * 100).fillna(0)
    grouped["PulledBrl%"] = (grouped["PulledBrl"] / grouped["BIP"] * 100).fillna(0)
    grouped["Brl/BIP%"] = (grouped["Barrels"] / grouped["BIP"] * 100).fillna(0)
    grouped["FB%"] = (grouped["FB"] / grouped["BIP"] * 100).fillna(0)
    grouped["HH%"] = (grouped["HH"] / grouped["BIP"] * 100).fillna(0)

    grouped["Pitch Score"] = (
        grouped["CSW%"] * 1.2 +
        grouped["SwStr%"] * 1.8 -
        grouped["Ball%"] * 0.5 -
        grouped["HH%"] * 0.35 -
        grouped["Brl/BIP%"] * 1.0
    ).clip(0, 100).round(1)

    grouped["Strikeout Score"] = (
        grouped["SwStr%"] * 4 +
        grouped["CSW%"] * 1.2 -
        grouped["Ball%"] * 0.4
    ).clip(0, 100).round(1)

    final = grouped[[
        "pitcher",
        "player_name",
        "Pitch Score",
        "Strikeout Score",
        "xwOBA",
        "CSW%",
        "SwStr%",
        "Ball%",
        "PulledBrl%",
        "Brl/BIP%",
        "FB%",
        "HH%",
    ]]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Saved pitcher metrics for {len(final)} pitchers")
    print(f"📁 {OUTPUT_FILE}")


if __name__ == "__main__":
    build_pitcher_metrics()