from pathlib import Path
import numpy as np
import pandas as pd

RAW_FILE = Path("data/raw/statcast/statcast_last_30_days.csv")
OUTPUT_FILE = Path("data/processed/pitch_mix_last_30_days.csv")


def safe_rate(numerator, denominator, multiplier=1):
    numerator = numerator.fillna(0)
    denominator = denominator.fillna(0)

    return np.where(
        denominator > 0,
        numerator / denominator * multiplier,
        0,
    )


def build_pitch_mix():
    df = pd.read_csv(RAW_FILE, low_memory=False)

    df = df[df["pitcher"].notna()]
    df = df[df["pitch_type"].notna()]

    grouped = df.groupby(
        ["pitcher", "player_name", "pitch_type"],
        dropna=False,
    ).agg(
        Pitches=("pitch_type", "count"),
        AvgVelo=("release_speed", "mean"),
        AvgSpin=("release_spin_rate", "mean"),
        AvgIVB=("pfx_z", "mean"),
        AvgHB=("pfx_x", "mean"),
    ).reset_index()

    totals = grouped.groupby("pitcher")["Pitches"].sum().reset_index()
    totals = totals.rename(columns={"Pitches": "TotalPitches"})

    grouped = grouped.merge(totals, on="pitcher", how="left")
    grouped["Usage%"] = safe_rate(grouped["Pitches"], grouped["TotalPitches"], 100)

    grouped = grouped.replace([np.inf, -np.inf], 0)
    grouped = grouped.fillna(0)

    grouped = grouped[[
        "pitcher",
        "player_name",
        "pitch_type",
        "Pitches",
        "TotalPitches",
        "Usage%",
        "AvgVelo",
        "AvgSpin",
        "AvgIVB",
        "AvgHB",
    ]]

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    grouped.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Saved pitch mix for {grouped['pitcher'].nunique()} pitchers")
    print(f"📁 {OUTPUT_FILE}")

    return grouped


if __name__ == "__main__":
    build_pitch_mix()