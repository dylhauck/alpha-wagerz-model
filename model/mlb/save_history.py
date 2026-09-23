from datetime import date
from pathlib import Path
import shutil

HISTORY_DIR = Path("data/history/mlb")
TODAY = date.today().isoformat()

FILES_TO_SAVE = [
    "data/processed/mlb/all_games.json",
    "data/processed/mlb/rankings.json",
    "data/processed/mlb/slate_summary.csv",
    "data/processed/mlb/weather.json",
    "data/processed/mlb/hitter_metrics_last_30_days.csv",
    "data/processed/mlb/pitcher_metrics_last_30_days.csv",
    "data/processed/mlb/team_offense_last_30_days.csv",
    "data/processed/mlb/bullpen_metrics_last_30_days.csv",
    "data/processed/mlb/pitch_arsenal_last_30_days.csv",
    "data/processed/mlb/pitcher_zone_allowed_last_30_days.csv",
]


def save_daily_history():
    output_dir = HISTORY_DIR / TODAY
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = 0

    for file in FILES_TO_SAVE:
        source = Path(file)

        if not source.exists():
            continue

        target = output_dir / source.name
        shutil.copy2(source, target)
        saved += 1

    print(f"✅ Saved {saved} history files to {output_dir}")


if __name__ == "__main__":
    save_daily_history()


