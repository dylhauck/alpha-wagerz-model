from pathlib import Path
import pandas as pd


RAW_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
OUTPUT_FILE = Path("data/processed/hitter_metrics_last_30_days.csv")


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


def build_hitter_metrics():
    df = pd.read_csv(RAW_FILE, low_memory=False)

    df["is_bip"] = df["type"] == "X"
    df["is_swinging_strike"] = df["description"].str.contains("swinging_strike", na=False)
    df["is_hard_hit"] = df["launch_speed"] >= 95
    df["is_sweet_spot"] = df["launch_angle"].between(8, 32)
    df["is_fly_ball"] = df["bb_type"].isin(["fly_ball", "popup"])
    df["is_barrel"] = df.apply(is_barrel, axis=1)
    df["total_bases"] = df["events"].apply(total_bases)

    at_bat_events = [
        "single", "double", "triple", "home_run",
        "field_out", "force_out", "grounded_into_double_play",
        "field_error", "strikeout", "strikeout_double_play",
        "fielders_choice", "fielders_choice_out",
        "double_play", "triple_play"
    ]

    df["is_ab"] = df["events"].isin(at_bat_events)
    df["is_hit"] = df["events"].isin(["single", "double", "triple", "home_run"])

    grouped = df.groupby(["batter", "player_name"], dropna=False).agg(
        Pitches=("pitch_type", "count"),
        BIP=("is_bip", "sum"),
        AB=("is_ab", "sum"),
        H=("is_hit", "sum"),
        TB=("total_bases", "sum"),
        xwOBA=("estimated_woba_using_speedangle", "mean"),
        xwOBAcon=("estimated_woba_using_speedangle", "mean"),
        SwStr=("is_swinging_strike", "sum"),
        PulledBrl=("is_barrel", "sum"),
        Barrels=("is_barrel", "sum"),
        SweetSpot=("is_sweet_spot", "sum"),
        FB=("is_fly_ball", "sum"),
        HH=("is_hard_hit", "sum"),
        LA=("launch_angle", "mean"),
    ).reset_index()

    grouped["ISO"] = ((grouped["TB"] - grouped["H"]) / grouped["AB"]).fillna(0)
    grouped["SwStr%"] = (grouped["SwStr"] / grouped["Pitches"] * 100).fillna(0)
    grouped["PulledBrl%"] = (grouped["PulledBrl"] / grouped["BIP"] * 100).fillna(0)
    grouped["Brl/BIP%"] = (grouped["Barrels"] / grouped["BIP"] * 100).fillna(0)
    grouped["Sweet Spot%"] = (grouped["SweetSpot"] / grouped["BIP"] * 100).fillna(0)
    grouped["FB%"] = (grouped["FB"] / grouped["BIP"] * 100).fillna(0)
    grouped["HH%"] = (grouped["HH"] / grouped["BIP"] * 100).fillna(0)

    final = grouped[[
        "batter",
        "player_name",
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
    ]]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Saved hitter metrics for {len(final)} players")
    print(f"📁 {OUTPUT_FILE}")


if __name__ == "__main__":
    build_hitter_metrics()