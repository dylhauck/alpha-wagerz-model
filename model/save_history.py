from datetime import date
from pathlib import Path
import shutil

HISTORY_DIR = Path("data/history")
TODAY = date.today().isoformat()

FILES_TO_SAVE = [
    "data/processed/all_games.json",
    "data/processed/rankings.json",
    "data/processed/slate_summary.csv",
    "data/processed/weather.json",
    "data/processed/hitter_metrics_last_30_days.csv",
    "data/processed/pitcher_metrics_last_30_days.csv",
    "data/processed/team_offense_last_30_days.csv",
    "data/processed/bullpen_metrics_last_30_days.csv",
    "data/processed/pitch_arsenal_last_30_days.csv",
    "data/processed/pitcher_zone_allowed_last_30_days.csv",
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