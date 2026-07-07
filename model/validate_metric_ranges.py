from pathlib import Path
import pandas as pd

FILES = [
    Path("data/processed/hitter_metrics_last_30_days.csv"),
    Path("data/processed/hitter_metrics_season.csv"),
    Path("data/processed/hitter_metrics_longterm.csv"),
]

KEY_COLUMNS = [
    "ISO",
    "xwOBA",
    "xwOBAcon",
    "PulledBrl%",
    "Brl/BIP%",
    "Sweet Spot%",
    "FB%",
    "HH%",
    "LA",
    "SwStr%",
]


def validate_metric_ranges():
    for file in FILES:
        if not file.exists():
            print(f"⚠️ Missing {file}")
            continue

        df = pd.read_csv(file)

        print()
        print(f"📊 {file}")
        print(f"Players: {len(df)}")

        for col in KEY_COLUMNS:
            if col not in df.columns:
                continue

            values = pd.to_numeric(df[col], errors="coerce").dropna()
            if values.empty:
                continue

            print(
                f"{col:14} "
                f"min={values.min():.3f} "
                f"p25={values.quantile(.25):.3f} "
                f"median={values.median():.3f} "
                f"p75={values.quantile(.75):.3f} "
                f"max={values.max():.3f}"
            )


if __name__ == "__main__":
    validate_metric_ranges()
