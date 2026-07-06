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
    ref["player_id"] = ref["player_id"].astype(str)

    return {
        str(row["player_id"]): row["player_name"]
        for _, row in ref.iterrows()
    }


def is_barrel(row):
    ev = row.get("launch_speed")
    la = row.get("launch_angle")

    if pd.isna(ev) or pd.isna(la):
        return False

    return ev >= 98 and 26 <= la <= 30


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

    df["player_name"] = df["batter"].map(player_lookup).fillna("")

    # Fallback to Statcast player_name if reference misses someone.
    if "player_name" in df.columns:
        df["player_name"] = df["player_name"].where(
            df["player_name"] != "",
            df["player_name"],
        )

    df = df[df["player_name"] != ""].copy()

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
        "double_play", "triple_play",
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

    longterm = build_metrics_from_file(
        RAW_LONGTERM_FILE,
        OUTPUT_LONGTERM_FILE,
        "longterm",
    )

    return last_30, season, longterm


if __name__ == "__main__":
    build_hitter_metrics()