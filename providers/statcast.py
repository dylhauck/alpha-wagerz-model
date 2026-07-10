from datetime import date, timedelta
from pathlib import Path

from pybaseball import statcast

RAW_DIR = Path("data/raw/statcast")

LAST_30_FILE = RAW_DIR / "statcast_last_30_days.csv"
SEASON_FILE = RAW_DIR / "statcast_season.csv"
LONGTERM_FILE = RAW_DIR / "statcast_longterm.csv"


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

    return pull_statcast_range(
        start_date,
        end_date,
        LAST_30_FILE,
    )


def get_statcast_season_events():
    end_date = date.today()
    start_date = date(end_date.year, 3, 1)

    return pull_statcast_range(
        start_date,
        end_date,
        SEASON_FILE,
    )


def get_statcast_longterm_events(years_back=1):
    end_date = date.today()
    start_date = date(end_date.year - years_back, 3, 1)

    return pull_statcast_range(
        start_date,
        end_date,
        LONGTERM_FILE,
    )


def get_all_statcast_events():
    print("\n📊 Pulling Last 30 Days Statcast...")
    get_statcast_batter_events()

    print("\n📊 Pulling Current Season Statcast...")
    get_statcast_season_events()

    print("\n📊 Pulling Long-Term Statcast (1 Seasons)...")
    get_statcast_longterm_events()


if __name__ == "__main__":
    get_all_statcast_events()