from datetime import date, timedelta
from pathlib import Path
import pandas as pd
from pybaseball import statcast


RAW_DIR = Path("data/raw/statcast")


def get_statcast_batter_events(days_back=30):
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    print(f"📥 Pulling Statcast data from {start_date} to {end_date}...")

    df = statcast(
        start_dt=start_date.isoformat(),
        end_dt=end_date.isoformat(),
    )

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    output_file = RAW_DIR / f"statcast_last_{days_back}_days.csv"
    df.to_csv(output_file, index=False)

    print(f"✅ Saved {len(df)} Statcast rows")
    print(f"📁 {output_file}")

    return df


if __name__ == "__main__":
    get_statcast_batter_events()