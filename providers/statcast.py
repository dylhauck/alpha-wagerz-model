from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from pybaseball import statcast

RAW_DIR = Path("data/raw/statcast")

LAST_30_FILE = RAW_DIR / "statcast_last_30_days.csv"
SEASON_FILE = RAW_DIR / "statcast_season.csv"
LONGTERM_FILE = RAW_DIR / "statcast_longterm.csv"

READ_CHUNK_SIZE = 100_000

_master_checked_for_date = None


def pull_statcast_range(start_date, end_date):
    """
    Pull a Statcast date range from Baseball Savant.
    """

    if start_date > end_date:
        return pd.DataFrame()

    print(f"📥 Pulling Statcast data from {start_date} to {end_date}...")

    df = statcast(
        start_dt=start_date.isoformat(),
        end_dt=end_date.isoformat(),
    )

    print(f"✅ Downloaded {len(df)} Statcast rows")

    return df


def save_statcast(df, output_file):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)

    print(f"✅ Saved {len(df)} Statcast rows")
    print(f"📁 {output_file}")


def get_csv_date_range(csv_file):
    """
    Read only game_date in chunks so the 1.7+ GB long-term master
    does not have to be loaded into memory just to find its range.
    """

    earliest = None
    latest = None

    for chunk in pd.read_csv(
        csv_file,
        usecols=["game_date"],
        chunksize=READ_CHUNK_SIZE,
        low_memory=False,
    ):
        dates = pd.to_datetime(
            chunk["game_date"],
            errors="coerce",
        ).dropna()

        if dates.empty:
            continue

        chunk_min = dates.min().date()
        chunk_max = dates.max().date()

        if earliest is None or chunk_min < earliest:
            earliest = chunk_min

        if latest is None or chunk_max > latest:
            latest = chunk_max

    return earliest, latest


def append_new_statcast_rows(master_file, new_df):
    """
    Append dates newer than the master without loading the historical
    1.7+ GB CSV into memory.

    Because the update begins on latest_game_date + 1, the appended
    rows cannot overlap dates already present in the master.
    """

    if new_df.empty:
        print("ℹ️ No new Statcast rows to append.")
        return

    master_columns = list(
        pd.read_csv(
            master_file,
            nrows=0,
            low_memory=False,
        ).columns
    )

    new_columns = list(new_df.columns)

    missing_columns = [
        column for column in master_columns
        if column not in new_columns
    ]

    extra_columns = [
        column for column in new_columns
        if column not in master_columns
    ]

    if missing_columns or extra_columns:
        raise RuntimeError(
            "Statcast schema changed. Refusing to append to the "
            "historical master because that could corrupt the dataset. "
            f"Missing columns: {missing_columns}. "
            f"New columns: {extra_columns}."
        )

    new_df = new_df[master_columns]

    new_df.to_csv(
        master_file,
        mode="a",
        header=False,
        index=False,
    )

    print(
        f"✅ Appended {len(new_df)} new rows to "
        f"{master_file}"
    )


def ensure_longterm_master_current(years_back=3):
    """
    Ensure the R2-restored long-term master exists and is current.

    The GitHub workflow restores statcast_longterm.csv before the
    pipeline starts. Normal daily runs therefore pull only dates newer
    than the newest date already stored in the master.
    """

    global _master_checked_for_date

    today = date.today()

    if _master_checked_for_date == today:
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    required_start_date = date(
        today.year - years_back,
        3,
        1,
    )

    if not LONGTERM_FILE.exists():
        raise FileNotFoundError(
            f"{LONGTERM_FILE} was not found. "
            "The GitHub Actions workflow must restore the Statcast "
            "master from R2 before running the model."
        )

    print(f"♻️ Using Statcast master: {LONGTERM_FILE}")

    earliest_date, latest_date = get_csv_date_range(
        LONGTERM_FILE
    )

    if earliest_date is None or latest_date is None:
        raise RuntimeError(
            f"{LONGTERM_FILE} does not contain valid game_date data."
        )

    print(
        f"📅 Statcast master range: "
        f"{earliest_date} to {latest_date}"
    )

    next_date = latest_date + timedelta(days=1)

    if next_date <= today:
        new_df = pull_statcast_range(
            next_date,
            today,
        )

        append_new_statcast_rows(
            LONGTERM_FILE,
            new_df,
        )
    else:
        print("✅ Statcast master is already current.")

    _master_checked_for_date = today


def build_window_from_master(
    output_file,
    start_date,
    end_date,
):
    """
    Build a smaller Statcast CSV from the long-term master in chunks.

    This keeps memory usage controlled while preserving every row and
    every column in the requested date window.
    """

    ensure_longterm_master_current()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    temp_file = output_file.with_suffix(
        output_file.suffix + ".tmp"
    )

    if temp_file.exists():
        temp_file.unlink()

    rows_written = 0
    wrote_header = False

    for chunk in pd.read_csv(
        LONGTERM_FILE,
        chunksize=READ_CHUNK_SIZE,
        low_memory=False,
    ):
        if "game_date" not in chunk.columns:
            raise RuntimeError(
                f"{LONGTERM_FILE} has no game_date column."
            )

        parsed_dates = pd.to_datetime(
            chunk["game_date"],
            errors="coerce",
        )

        mask = (
            parsed_dates.notna()
            & (parsed_dates.dt.date >= start_date)
            & (parsed_dates.dt.date <= end_date)
        )

        window_chunk = chunk.loc[mask]

        if window_chunk.empty:
            continue

        window_chunk.to_csv(
            temp_file,
            mode="a",
            header=not wrote_header,
            index=False,
        )

        wrote_header = True
        rows_written += len(window_chunk)

    if not wrote_header:
        columns = list(
            pd.read_csv(
                LONGTERM_FILE,
                nrows=0,
                low_memory=False,
            ).columns
        )

        pd.DataFrame(
            columns=columns
        ).to_csv(
            temp_file,
            index=False,
        )

    temp_file.replace(output_file)

    print(f"✅ Saved {rows_written} Statcast rows")
    print(f"📁 {output_file}")

    return output_file


def get_statcast_batter_events(days_back=30):
    """
    Build the last-N-days dataset from the full historical master.

    No separate 30-day Baseball Savant download is required.
    """

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    print(
        f"📊 Building last-{days_back}-day Statcast "
        f"dataset from master..."
    )

    return build_window_from_master(
        LAST_30_FILE,
        start_date,
        end_date,
    )


def get_statcast_season_events():
    """
    Build the current-season dataset from the full historical master.

    No separate season-long Baseball Savant download is required.
    """

    end_date = date.today()
    start_date = date(
        end_date.year,
        3,
        1,
    )

    print(
        "📊 Building current-season Statcast "
        "dataset from master..."
    )

    return build_window_from_master(
        SEASON_FILE,
        start_date,
        end_date,
    )


def get_statcast_longterm_events(years_back=3):
    """
    Keep the full long-term Statcast master current.

    The existing project convention is preserved:
        March 1 of current_year - years_back
        through today.

    The master itself is persisted by the GitHub workflow in R2.
    """

    ensure_longterm_master_current(
        years_back=years_back
    )

    return LONGTERM_FILE


def get_all_statcast_events():
    print("\n📊 Building Last 30 Days Statcast...")
    get_statcast_batter_events()

    print("\n📊 Building Current Season Statcast...")
    get_statcast_season_events()

    print("\n📊 Updating Long-Term Statcast...")
    get_statcast_longterm_events()


if __name__ == "__main__":
    get_all_statcast_events()
