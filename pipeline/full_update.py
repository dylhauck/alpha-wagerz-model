from graphics.create_weather_graphic import create_weather_graphic
from providers.mlb_reference import build_reference_files
from providers.mlb_players import build_player_reference
from providers.statcast import get_statcast_batter_events
from providers.weather import build_weather_file
from providers.pitch_mix import build_pitch_mix

from scripts.update_today import main as update_today

from model.attach_weather import attach_weather_to_games
from model.hitter_metrics import build_hitter_metrics
from model.pitcher_metrics import build_pitcher_metrics
from model.hitter_pitch_type_metrics import build_hitter_pitch_type_metrics
from model.attach_pitcher_metrics import attach_pitcher_metrics_to_games
from model.attach_pitch_type_matchups import attach_pitch_type_matchups
from model.attach_hitter_metrics import attach_hitter_metrics_to_games
from model.enrich_players import enrich_players_in_games
from model.rankings import build_rankings
from model.build_all_games import build_all_games
from model.validate_pipeline import validate_pipeline
from model.team_offense_metrics import build_team_offense_metrics
from model.attach_team_context import attach_team_context

from google_sheets.update_full_slate import update_full_slate_sheets
from model.bullpen_metrics import build_bullpen_metrics
from model.attach_bullpen_context import attach_bullpen_context
from model.validate_model_features import validate_model_features
from model.pitch_arsenal_metrics import build_pitch_arsenal_metrics
from model.zone_allowed_metrics import build_zone_allowed_metrics
from model.save_history import save_daily_history
from model.publish_to_web import publish_to_web
from providers.standings import build_team_context_file
from model.attach_team_standings import attach_team_standings
from model.attach_game_times import attach_game_times
from model.export_hr_graphic_data import export_hr_graphic_data
from graphics.create_hr_targets_graphic import create_graphic
from model.export_game_projections import export_game_projections
from providers.market import build_market_lines
from providers.market import build_market_lines

def run_full_update():
    print("🐺 Starting Alpha Wagerz full update...")

    print("\n📚 Reference data")
    build_reference_files()
    build_player_reference()

    print("\n🗓️ Slate / lineups")
    update_today()
    build_team_context_file()

    print("\n📊 Statcast")
    get_statcast_batter_events()

    print("\n🌤️ Weather")
    build_weather_file()
    attach_weather_to_games()

    print("\n⚾ Metrics")
    build_hitter_metrics()
    build_pitcher_metrics()
    build_pitch_mix()
    build_hitter_pitch_type_metrics()
    build_pitch_arsenal_metrics()
    build_zone_allowed_metrics()
    build_team_offense_metrics()
    build_bullpen_metrics()

    print("\n🔗 Attachments")

    attach_pitcher_metrics_to_games()
    attach_pitch_type_matchups()
    attach_team_context()
    attach_bullpen_context()
    attach_hitter_metrics_to_games()
    enrich_players_in_games()
    attach_game_times()          # NEW
    attach_team_standings()

    print("\n💰 Market Lines")
    build_market_lines()

    print("\n🏆 Outputs")
    build_rankings()
    build_all_games()
    export_game_projections()
    export_hr_graphic_data()
    create_graphic()
    create_weather_graphic()

    print("\n🔎 Validation")
    validate_pipeline()
    validate_model_features()

    print("\n📄 Google Sheets")
    update_full_slate_sheets()

    print("\n🗄️ Saving history")
    save_daily_history()

    print("\n🌐 Publishing web data")
    publish_to_web()

    print("\n✅ Alpha Wagerz full update complete.")