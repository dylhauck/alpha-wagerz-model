from providers.mlb import get_todays_slate
from providers.lineups import get_official_lineups
from utils.file_utils import save_json
from scripts.build_game_files import build_game_files
from scripts.build_game_index import build_game_index
from model.attach_lineups import attach_lineups_to_games
import pandas as pd


def main():
    print("📥 Pulling today's MLB slate...")

    slate = get_todays_slate()
    save_json(slate, "data/raw/todays_slate.json")

    df = pd.DataFrame(slate)
    df.to_csv("data/processed/slate_summary.csv", index=False)

    print(f"✅ Saved slate with {len(slate)} games")

    build_game_files()
    build_game_index()

    print("📥 Pulling official MLB lineups...")
    get_official_lineups()

    print("🔗 Attaching lineups to game files...")
    attach_lineups_to_games()

    print("🐺 Alpha Wagerz daily MLB build complete.")


if __name__ == "__main__":
    main()