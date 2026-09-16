from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from pybaseball import statcast

RAW_DIR = Path("data/raw/statcast")

LAST_30_FILE = RAW_DIR / "statcast_last_30_days.csv"
SEASON_FILE = RAW_DIR / "statcast_season.csv"
LONGTERM_FILE = RAW_DIR / "statcast_longterm.csv"


def pull_statcast_range(start_date, end_date):
    """
    Pull a Statcast date range from Baseball Savant.
    Does not save the file itself.
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


def get_latest_game_date(df):
    """
    Return the newest game_date contained in a Statcast dataframe.
    """

    if df.empty or "game_date" not in df.columns:
        return None

    game_dates = pd.to_datetime(
        df["game_date"],
        errors="coerce",
    ).dropna()

    if game_dates.empty:
        return None

    return game_dates.max().date()


def merge_statcast(existing_df, new_df):
    """
    Merge existing and newly downloaded Statcast data.

    Statcast's sv_id is used when available because it identifies
    individual pitches. If sv_id is unavailable, exact duplicate
    rows are removed instead.
    """

    if existing_df.empty:
        combined = new_df.copy()
    elif new_df.empty:
        combined = existing_df.copy()
    else:
        combined = pd.concat(
            [existing_df, new_df],
            ignore_index=True,
        )

    if combined.empty:
        return combined

    if "sv_id" in combined.columns:
        combined = combined.drop_duplicates(
            subset=["sv_id"],
            keep="last",
        )
    else:
        combined = combined.drop_duplicates(
            keep="last",
        )

    if "game_date" in combined.columns:
        combined["_sort_game_date"] = pd.to_datetime(
            combined["game_date"],
            errors="coerce",
        )

        combined = combined.sort_values(
            "_sort_game_date"
        ).drop(
            columns=["_sort_game_date"]
        )

    return combined.reset_index(drop=True)


def update_incremental_statcast(
    output_file,
    required_start_date,
    end_date,
):
    """
    Build a Statcast dataset once, then incrementally update it.

    If a cached file exists:
      1. Load it.
      2. Make sure it reaches back to required_start_date.
      3. Pull only dates newer than the newest cached game_date.
      4. Merge and deduplicate.

    If no cached file exists:
      Pull the complete required range once.
    """

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not output_file.exists():
        print(f"🆕 No cached Statcast file found: {output_file}")
        print("📦 Building initial dataset...")

        df = pull_statcast_range(
            required_start_date,
            end_date,
        )

        save_statcast(
            df,
            output_file,
        )

        return df

    print(f"♻️ Loading cached Statcast data: {output_file}")

    try:
        existing_df = pd.read_csv(
            output_file,
            low_memory=False,
        )
    except Exception as exc:
        print(f"⚠️ Could not read cached Statcast file: {exc}")
        print("📦 Rebuilding dataset...")

        df = pull_statcast_range(
            required_start_date,
            end_date,
        )

        save_statcast(
            df,
            output_file,
        )

        return df

    print(f"📊 Cached rows: {len(existing_df)}")

    if existing_df.empty:
        print("⚠️ Cached file is empty. Rebuilding...")

        df = pull_statcast_range(
            required_start_date,
            end_date,
        )

        save_statcast(
            df,
            output_file,
        )

        return df

    if "game_date" not in existing_df.columns:
        print("⚠️ Cached file has no game_date column. Rebuilding...")

        df = pull_statcast_range(
            required_start_date,
            end_date,
        )

        save_statcast(
            df,
            output_file,
        )

        return df

    game_dates = pd.to_datetime(
        existing_df["game_date"],
        errors="coerce",
    ).dropna()

    if game_dates.empty:
        print("⚠️ Cached file has no valid game dates. Rebuilding...")

        df = pull_statcast_range(
            required_start_date,
            end_date,
        )

        save_statcast(
            df,
            output_file,
        )

        return df

    earliest_cached_date = game_dates.min().date()
    latest_cached_date = game_dates.max().date()

    print(
        f"📅 Cached range: "
        f"{earliest_cached_date} to {latest_cached_date}"
    )

    combined_df = existing_df

    # ---------------------------------------------------------
    # BACKFILL
    # ---------------------------------------------------------
    # This matters if an older/incomplete cache gets restored.
    # We fill anything required before its earliest cached date.
    # ---------------------------------------------------------

    if earliest_cached_date > required_start_date:
        backfill_end = earliest_cached_date - timedelta(days=1)

        print(
            f"📥 Backfilling missing Statcast data "
            f"from {required_start_date} to {backfill_end}..."
        )

        backfill_df = pull_statcast_range(
            required_start_date,
            backfill_end,
        )

        combined_df = merge_statcast(
            combined_df,
            backfill_df,
        )

    # ---------------------------------------------------------
    # FORWARD UPDATE
    # ---------------------------------------------------------

    latest_date = get_latest_game_date(combined_df)

    if latest_date is None:
        next_date = required_start_date
    else:
        next_date = latest_date + timedelta(days=1)

    if next_date <= end_date:
        print(
            f"📥 Pulling new Statcast data "
            f"from {next_date} to {end_date}..."
        )

        new_df = pull_statcast_range(
            next_date,
            end_date,
        )

        combined_df = merge_statcast(
            combined_df,
            new_df,
        )

    else:
        print("✅ Cached Statcast data is already current.")

    # Keep only the requested historical window.
    if "game_date" in combined_df.columns:
        parsed_dates = pd.to_datetime(
            combined_df["game_date"],
            errors="coerce",
        )

        mask = (
            parsed_dates.notna()
            & (parsed_dates.dt.date >= required_start_date)
            & (parsed_dates.dt.date <= end_date)
        )

        combined_df = combined_df.loc[mask].copy()

    save_statcast(
        combined_df,
        output_file,
    )

    return combined_df


def get_statcast_batter_events(days_back=30):
    """
    Last 30 days stays a normal fresh pull.

    This dataset is relatively small and we want it rebuilt from
    Baseball Savant each day.
    """

    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)

    print(
        f"📊 Building fresh last-{days_back}-day "
        f"Statcast dataset..."
    )

    df = pull_statcast_range(
        start_date,
        end_date,
    )

    save_statcast(
        df,
        LAST_30_FILE,
    )

    return df


def get_statcast_season_events():
    """
    Current-season Statcast.

    Restored from the GitHub Actions cache when available and
    incrementally updated with only newly available dates.
    """

    end_date = date.today()
    start_date = date(
        end_date.year,
        3,
        1,
    )

    return update_incremental_statcast(
        SEASON_FILE,
        start_date,
        end_date,
    )


def get_statcast_longterm_events(years_back=3):
    """
    Long-term Statcast.

    Keeps the current season plus the previous three years based
    on the existing project convention:

        current_year - years_back, March 1
            through
        today

    The historical dataset is restored from GitHub Actions cache
    and only missing/new dates are downloaded.
    """

    end_date = date.today()

    start_date = date(
        end_date.year - years_back,
        3,
        1,
    )

    return update_incremental_statcast(
        LONGTERM_FILE,
        start_date,
        end_date,
    )


def get_all_statcast_events():
    print("\n📊 Pulling Last 30 Days Statcast...")
    get_statcast_batter_events()

    print("\n📊 Updating Current Season Statcast...")
    get_statcast_season_events()

    print("\n📊 Updating Long-Term Statcast...")
    get_statcast_longterm_events()


if __name__ == "__main__":
    get_all_statcast_events()