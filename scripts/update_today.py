from pathlib import Path
import shutil

import pandas as pd

from providers.mlb import get_todays_slate
from providers.lineups import build_lineups

from utils.file_utils import save_json

from scripts.build_game_files import build_game_files
from scripts.build_game_index import build_game_index

from model.attach_lineups import attach_lineups_to_games


GAMES_DIR = Path("data/processed/games")


def clear_old_games():
    """
    Delete yesterday's processed game files before building today's slate.
    This prevents stale games from remaining in the model.
    """
    if GAMES_DIR.exists():
        shutil.rmtree(GAMES_DIR)

    GAMES_DIR.mkdir(parents=True, exist_ok=True)

    print("🗑️ Cleared previous game files")


def main():
    # Always start fresh
    clear_old_games()

    print("📥 Pulling today's MLB slate...")

    slate = get_todays_slate()

    save_json(slate, "data/raw/todays_slate.json")

    pd.DataFrame(slate).to_csv(
        "data/processed/slate_summary.csv",
        index=False,
    )

    print(f"✅ Saved slate with {len(slate)} games")

    print("🗂️ Building game files...")
    build_game_files()

    print("📋 Building game index...")
    build_game_index()

    print("📥 Pulling official MLB lineups...")
    build_lineups()

    print("🔗 Attaching lineups to game files...")
    attach_lineups_to_games()

    print("🐺 Alpha Wagerz daily MLB build complete.")


if __name__ == "__main__":
    main()