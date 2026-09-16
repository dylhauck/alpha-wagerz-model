from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from pybaseball import statcast

RAW_DIR = Path("data/raw/statcast")

LAST_30_FILE = RAW_DIR / "statcast_last_30_days.csv"
SEASON_FILE = RAW_DIR / "statcast_season.csv"
LONGTERM_FILE = RAW_DIR / "statcast_longterm.csv"
METADATA_FILE = RAW_DIR / "statcast_master_metadata.txt"

READ_CHUNK_SIZE = 150_000

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


def read_metadata_date():
    """
    Read the newest game_date recorded for the R2 master.

    This avoids scanning the entire 1.7+ GB CSV on normal daily runs.
    The first optimized run may not have metadata yet; in that case
    we scan the master once and create it.
    """

    if not METADATA_FILE.exists():
        return None

    try:
        value = METADATA_FILE.read_text(encoding="utf-8").strip()
        return date.fromisoformat(value)
    except Exception:
        return None


def write_metadata_date(latest_date):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_FILE.write_text(
        latest_date.isoformat(),
        encoding="utf-8",
    )


def scan_master_latest_date():
    """
    One-time fallback used only when metadata does not yet exist.
    Reads only game_date in chunks.
    """

    latest = None

    for chunk in pd.read_csv(
        LONGTERM_FILE,
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

        chunk_latest = dates.max().date()

        if latest is None or chunk_latest > latest:
            latest = chunk_latest

    return latest


def append_new_statcast_rows(new_df):
    """
    Append only dates newer than the historical master.

    The pull begins at latest_game_date + 1, so normal daily updates
    do not overlap dates already stored in the master.
    """

    if new_df.empty:
        print("ℹ️ No new Statcast rows to append.")
        return

    master_columns = list(
        pd.read_csv(
            LONGTERM_FILE,
            nrows=0,
            low_memory=False,
        ).columns
    )

    new_columns = list(new_df.columns)

    missing_columns = [
        column
        for column in master_columns
        if column not in new_columns
    ]
    extra_columns = [
        column
        for column in new_columns
        if column not in master_columns
    ]

    if missing_columns or extra_columns:
        raise RuntimeError(
            "Statcast schema changed. Refusing to append because that "
            "could corrupt the historical master. "
            f"Missing columns: {missing_columns}. "
            f"New columns: {extra_columns}."
        )

    new_df = new_df[master_columns]

    new_df.to_csv(
        LONGTERM_FILE,
        mode="a",
        header=False,
        index=False,
    )

    print(
        f"✅ Appended {len(new_df)} new rows to "
        f"{LONGTERM_FILE}"
    )


def ensure_longterm_master_current():
    """
    Make the R2-restored historical master current.

    Normal runs use the metadata file to know the newest stored date,
    so they do not scan the entire historical CSV just to find it.
    """

    global _master_checked_for_date

    today = date.today()

    if _master_checked_for_date == today:
        return

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not LONGTERM_FILE.exists():
        raise FileNotFoundError(
            f"{LONGTERM_FILE} was not found. "
            "The GitHub Actions workflow must restore the Statcast "
            "master from R2 before running the model."
        )

    latest_date = read_metadata_date()

    if latest_date is None:
        print(
            "ℹ️ Statcast metadata not found. "
            "Scanning master once to initialize it..."
        )
        latest_date = scan_master_latest_date()

        if latest_date is None:
            raise RuntimeError(
                f"{LONGTERM_FILE} does not contain valid game_date data."
            )

        write_metadata_date(latest_date)

    print(f"📅 Statcast master newest date: {latest_date}")

    next_date = latest_date + timedelta(days=1)

    if next_date <= today:
        new_df = pull_statcast_range(
            next_date,
            today,
        )

        append_new_statcast_rows(new_df)

        if not new_df.empty and "game_date" in new_df.columns:
            new_dates = pd.to_datetime(
                new_df["game_date"],
                errors="coerce",
            ).dropna()

            if not new_dates.empty:
                latest_date = max(
                    latest_date,
                    new_dates.max().date(),
                )

        # Even on off-days/no-data days, keep the actual newest
        # game_date rather than falsely advancing the metadata.
        write_metadata_date(latest_date)
    else:
        print("✅ Statcast master is already current.")

    _master_checked_for_date = today


def build_recent_and_season_from_master(days_back=30):
    """
    Build last-30-days and current-season files in ONE pass through
    the historical master.

    This replaces two separate full scans of the 1.7+ GB CSV.
    """

    ensure_longterm_master_current()

    today = date.today()
    recent_start = today - timedelta(days=days_back)
    season_start = date(today.year, 3, 1)

    recent_temp = LAST_30_FILE.with_suffix(".csv.tmp")
    season_temp = SEASON_FILE.with_suffix(".csv.tmp")

    for temp_file in (recent_temp, season_temp):
        if temp_file.exists():
            temp_file.unlink()

    recent_rows = 0
    season_rows = 0
    recent_header_written = False
    season_header_written = False

    print(
        "📊 Building last-30-days and current-season Statcast "
        "datasets in one master pass..."
    )

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

        valid = parsed_dates.notna()

        season_mask = (
            valid
            & (parsed_dates.dt.date >= season_start)
            & (parsed_dates.dt.date <= today)
        )

        recent_mask = (
            valid
            & (parsed_dates.dt.date >= recent_start)
            & (parsed_dates.dt.date <= today)
        )

        season_chunk = chunk.loc[season_mask]
        recent_chunk = chunk.loc[recent_mask]

        if not season_chunk.empty:
            season_chunk.to_csv(
                season_temp,
                mode="a",
                header=not season_header_written,
                index=False,
            )
            season_header_written = True
            season_rows += len(season_chunk)

        if not recent_chunk.empty:
            recent_chunk.to_csv(
                recent_temp,
                mode="a",
                header=not recent_header_written,
                index=False,
            )
            recent_header_written = True
            recent_rows += len(recent_chunk)

    master_columns = None

    if not season_header_written or not recent_header_written:
        master_columns = list(
            pd.read_csv(
                LONGTERM_FILE,
                nrows=0,
                low_memory=False,
            ).columns
        )

    if not season_header_written:
        pd.DataFrame(
            columns=master_columns
        ).to_csv(
            season_temp,
            index=False,
        )

    if not recent_header_written:
        pd.DataFrame(
            columns=master_columns
        ).to_csv(
            recent_temp,
            index=False,
        )

    season_temp.replace(SEASON_FILE)
    recent_temp.replace(LAST_30_FILE)

    print(f"✅ Season rows: {season_rows}")
    print(f"📁 {SEASON_FILE}")
    print(f"✅ Last-{days_back}-days rows: {recent_rows}")
    print(f"📁 {LAST_30_FILE}")


def get_statcast_batter_events(days_back=30):
    """
    Ensure both derived datasets exist, then return the recent path.

    The project's downstream metric builders read the CSV files from
    disk, so returning the path avoids loading a large dataframe here.
    """

    build_recent_and_season_from_master(
        days_back=days_back
    )
    return LAST_30_FILE


def get_statcast_season_events():
    """
    The season file is produced together with the recent file during
    the first Statcast call in the full update.
    """

    if not SEASON_FILE.exists():
        build_recent_and_season_from_master()

    return SEASON_FILE


def get_statcast_longterm_events(years_back=3):
    """
    Preserve the complete historical master and update it forward.

    years_back is retained for compatibility with existing callers;
    the persisted R2 master itself remains the source of truth.
    """

    ensure_longterm_master_current()
    return LONGTERM_FILE


def get_all_statcast_events():
    print("\n📊 Updating Statcast master and derived datasets...")
    build_recent_and_season_from_master(days_back=30)

    print("\n📊 Statcast datasets ready:")
    print(f"📁 {LAST_30_FILE}")
    print(f"📁 {SEASON_FILE}")
    print(f"📁 {LONGTERM_FILE}")


if __name__ == "__main__":
    get_all_statcast_events()
