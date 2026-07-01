from datetime import date, timedelta
from pathlib import Path

from pybaseball import statcast

RAW_DIR = Path("data/raw/statcast")


def pull_statcast_range(start_date, end_date, output_file):
    print(f"📥 Pulling Statcast data from {start_date} to {end_date}...")

    df = statcast(
        start_dt=start_date.isoformat(),
        end_dt=end_date.isoformat(),
    )

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)

    print(f"✅ Saved {len(df)} Statcast rows")
    print(f"📁 {output_file}")

    return df


def get_statcast_batter_events(days_back=30):
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    output_file = RAW_DIR / f"statcast_last_{days_back}_days.csv"

    return pull_statcast_range(start_date, end_date, output_file)


def get_statcast_season_events():
    end_date = date.today()
    start_date = date(end_date.year, 3, 1)

    output_file = RAW_DIR / "statcast_season.csv"

    return pull_statcast_range(start_date, end_date, output_file)


def get_all_statcast_events():
    get_statcast_batter_events()
    get_statcast_season_events()


if __name__ == "__main__":
    get_all_statcast_events()