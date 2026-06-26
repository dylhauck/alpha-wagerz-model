from scripts.update_today import main as update_today
from providers.statcast import get_statcast_batter_events
from model.hitter_metrics import build_hitter_metrics
from model.pitcher_metrics import build_pitcher_metrics
from model.attach_hitter_metrics import attach_hitter_metrics_to_games
from model.attach_pitcher_metrics import attach_pitcher_metrics_to_games
from model.rankings import build_rankings
from google_sheets.rankings_writer import update_rankings_sheet


def main():
    print("🐺 Starting Alpha Wagerz full update...")

    update_today()
    get_statcast_batter_events()
    build_hitter_metrics()
    build_pitcher_metrics()
    attach_hitter_metrics_to_games()
    attach_pitcher_metrics_to_games()
    build_rankings()
    update_rankings_sheet()

    print("✅ Alpha Wagerz full update complete.")


if __name__ == "__main__":
    main()