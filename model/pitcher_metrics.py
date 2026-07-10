from pathlib import Path
import numpy as np
import pandas as pd

RAW_LAST_30_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
RAW_SEASON_FILE = Path("data/raw/statcast/statcast_season.csv")
RAW_LONGTERM_FILE = Path("data/raw/statcast/statcast_longterm.csv")

OUTPUT_LAST_30_FILE = Path("data/processed/pitcher_metrics_last_30_days.csv")
OUTPUT_SEASON_FILE = Path("data/processed/pitcher_metrics_season.csv")
OUTPUT_LONGTERM_FILE = Path("data/processed/pitcher_metrics_longterm.csv")


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


def build_metrics_from_file(raw_file, output_file, label):
    if not raw_file.exists():
        print(f"⚠️ Missing {raw_file}. Skipping {label} pitcher metrics.")
        return pd.DataFrame()

    df = pd.read_csv(raw_file, low_memory=False)
    df = df[df["pitcher"].notna()].copy()

    if "pitcher_name" in df.columns:
        df["pitcher_display_name"] = df["pitcher_name"]
    else:
        df["pitcher_display_name"] = df["player_name"]

    df["is_bip"] = df["type"] == "X"
    df["is_called_strike"] = df["description"].str.contains("called_strike", na=False)
    df["is_swinging_strike"] = df["description"].str.contains("swinging_strike", na=False)
    df["is_csw"] = df["is_called_strike"] | df["is_swinging_strike"]
    df["is_ball"] = df["description"].str.contains("ball", na=False)
    df["is_hard_hit"] = df["launch_speed"] >= 95
    df["is_barrel"] = df.apply(is_barrel, axis=1)
    df["is_fly_ball"] = df["bb_type"].isin(["fly_ball", "popup"])
    df["is_ground_ball"] = df["bb_type"] == "ground_ball"
    df["is_hr"] = df["events"] == "home_run"
    df["is_k"] = df["events"].isin(["strikeout", "strikeout_double_play"])
    df["is_bb"] = df["events"].isin(["walk", "intent_walk"])

    pa_events = [
        "single", "double", "triple", "home_run",
        "field_out", "force_out", "grounded_into_double_play",
        "field_error", "strikeout", "strikeout_double_play",
        "fielders_choice", "fielders_choice_out",
        "double_play", "triple_play",
        "walk", "intent_walk", "hit_by_pitch", "sac_fly", "sac_bunt",
    ]

    df["is_pa"] = df["events"].isin(pa_events)

    grouped = df.groupby(["pitcher", "pitcher_display_name"], dropna=False).agg(
        Pitches=("pitch_type", "count"),
        BF=("is_pa", "sum"),
        BIP=("is_bip", "sum"),
        HR=("is_hr", "sum"),
        K=("is_k", "sum"),
        BB=("is_bb", "sum"),
        xwOBA=("estimated_woba_using_speedangle", "mean"),
        xwOBAcon=("estimated_woba_using_speedangle", "mean"),
        CSW=("is_csw", "sum"),
        SwStr=("is_swinging_strike", "sum"),
        Ball=("is_ball", "sum"),
        Barrels=("is_barrel", "sum"),
        HH=("is_hard_hit", "sum"),
        FB=("is_fly_ball", "sum"),
        GB=("is_ground_ball", "sum"),
        AvgEV=("launch_speed", "mean"),
        AvgLA=("launch_angle", "mean"),
        FBv=("release_speed", "mean"),
    ).reset_index()

    grouped = grouped.rename(columns={"pitcher_display_name": "player_name"})

    grouped["CSW%"] = safe_rate(grouped["CSW"], grouped["Pitches"], 100)
    grouped["SwStr%"] = safe_rate(grouped["SwStr"], grouped["Pitches"], 100)
    grouped["Ball%"] = safe_rate(grouped["Ball"], grouped["Pitches"], 100)
    grouped["Brl/BIP%"] = safe_rate(grouped["Barrels"], grouped["BIP"], 100)
    grouped["PulledBrl%"] = grouped["Brl/BIP%"]
    grouped["HH%"] = safe_rate(grouped["HH"], grouped["BIP"], 100)
    grouped["FB%"] = safe_rate(grouped["FB"], grouped["BIP"], 100)
    grouped["GB%"] = safe_rate(grouped["GB"], grouped["BIP"], 100)
    grouped["K%"] = safe_rate(grouped["K"], grouped["BF"], 100)
    grouped["BB%"] = safe_rate(grouped["BB"], grouped["BF"], 100)

    grouped["IP"] = grouped["BF"] / 3
    grouped["HR/9"] = safe_rate(grouped["HR"], grouped["IP"], 9)

    grouped["Pitch Score"] = (
        100
        - grouped["xwOBA"].fillna(0) * 85
        - grouped["Brl/BIP%"] * 1.2
        - grouped["HH%"] * 0.35
        - grouped["FB%"] * 0.25
        - grouped["Ball%"] * 0.20
        + grouped["SwStr%"] * 0.55
    ).clip(0, 100)

    grouped["Strikeout Score"] = (
        grouped["SwStr%"] * 2.4
        + grouped["CSW%"] * 1.5
        - grouped["Ball%"] * 0.35
        + grouped["K%"] * 0.35
    ).clip(0, 100)

    grouped["HR Vulnerability"] = (
        grouped["HR/9"] * 10
        + grouped["Brl/BIP%"] * 1.5
        + grouped["HH%"] * 0.55
        + grouped["FB%"] * 0.35
        + grouped["xwOBAcon"].fillna(0) * 60
    ).clip(0, 100)

    grouped = grouped.rename(
        columns={
            "xwOBA": "Pitcher xwOBA",
            "xwOBAcon": "Pitcher xwOBAcon",
        }
    )

    final = grouped[
        [
            "pitcher",
            "player_name",
            "Pitches",
            "BF",
            "IP",
            "HR",
            "K",
            "BB",
            "Pitcher xwOBA",
            "Pitcher xwOBAcon",
            "CSW%",
            "SwStr%",
            "Ball%",
            "PulledBrl%",
            "Brl/BIP%",
            "FB%",
            "GB%",
            "HH%",
            "K%",
            "BB%",
            "HR/9",
            "AvgEV",
            "AvgLA",
            "FBv",
            "Pitch Score",
            "Strikeout Score",
            "HR Vulnerability",
        ]
    ].copy()

    final = final.replace([np.inf, -np.inf], 0).fillna(0)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    final.to_csv(output_file, index=False)

    print(f"✅ Saved {label} pitcher metrics for {len(final)} pitchers")
    print(f"📁 {output_file}")

    return final


def build_pitcher_metrics():
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

    longterm = build_metrics_from_file(
        RAW_LONGTERM_FILE,
        OUTPUT_LONGTERM_FILE,
        "longterm",
    )

    return last_30, season, longterm


if __name__ == "__main__":
    build_pitcher_metrics()