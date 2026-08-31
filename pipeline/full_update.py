from graphics.create_weather_graphic import create_weather_graphic
from model.nfl.injury_context import build_nfl_injury_context
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
from providers.espn_injuries import build_injury_report
from pipeline.tomorrow_update import run_tomorrow_update

# NFL
from providers.nfl_data import build_all_nfl_data
from providers.nfl_matchups import build_nfl_matchups
from providers.nfl_injuries import build_nfl_injuries
from providers.nfl_weather import build_nfl_weather
from providers.nfl_market import build_nfl_market

from model.nfl.team_metrics import build_team_metrics
from model.nfl.player_metrics import build_nfl_player_metrics
from model.nfl.matchup_metrics import build_nfl_matchup_metrics
from model.nfl.injury_context import build_nfl_injury_context
from model.nfl.game_projections import build_nfl_game_projections
from model.nfl.player_projections import build_nfl_player_projections
from model.nfl.edge_engine import build_nfl_edges
from providers.nfl_player_props import build_nfl_player_props
from model.nfl.player_prop_edges import build_nfl_player_prop_edges
from providers.nfl_odds import build_nfl_odds
from model.nfl.rankings import build_nfl_rankings

def run_full_update():
    print("🐺 Starting Alpha Wagerz full update...")

    # =========================================================
    # MLB
    # =========================================================

    print("\n📚 Reference data")
    build_reference_files()
    build_player_reference()

    print("\n🗓️ Slate / lineups")
    update_today()
    build_team_context_file()

    print("\n🏥 Injury report")
    build_injury_report()

    print("\n📊 Statcast")
    get_statcast_batter_events()

    print("\n🌤️ Weather")
    build_weather_file()

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

    attach_weather_to_games()
    attach_team_context()
    attach_bullpen_context()
    attach_team_standings()
    attach_game_times()

    attach_hitter_metrics_to_games()
    attach_pitch_type_matchups()

    attach_pitcher_metrics_to_games()

    enrich_players_in_games()

    print("\n🏗️ Building combined game data")
    build_all_games()

    print("\n💰 Market Lines")
    build_market_lines()

    print("\n🏆 Outputs")
    build_rankings()
    export_game_projections()
    export_hr_graphic_data()
    create_graphic()
    create_weather_graphic()

    print("\n🔎 Validation")
    validate_pipeline()
    validate_model_features()

    print("\n🌐 Publishing web data")
    publish_to_web()

    print("\n🌙 Tomorrow's Slate")
    run_tomorrow_update()

    print("\n📄 Google Sheets")
    update_full_slate_sheets()

    print("\n🗄️ Saving history")
    save_daily_history()

    # =========================================================
    # NFL
    # =========================================================

    print("\n🏈 NFL Data")
    build_all_nfl_data()

    print("\n🏥 NFL Injuries")
    build_nfl_injuries()

    print("\n📊 NFL Team Metrics")
    build_team_metrics()

    print("\n👤 NFL Player Metrics")
    build_nfl_player_metrics()

    print("\n⚔️ NFL Matchup History")
    build_nfl_matchups()

    print("\n🧠 NFL Matchup Metrics")
    build_nfl_matchup_metrics()

    print("\n🏥 NFL Injury Context")
    build_nfl_injury_context()

    print("\n🌦️ NFL Weather")
    build_nfl_weather()

    print("\n🎯 NFL Game Projections")
    build_nfl_game_projections()

    print("\n🏃 NFL Player Projections")
    build_nfl_player_projections()

    print("\n📡 Live NFL Odds")
    build_nfl_odds()

    print("\n💰 NFL Market")
    build_nfl_market()

    print("\n📈 NFL Edges & Confidence")
    build_nfl_edges()

    print("\n🏷️ NFL Player Props")
    build_nfl_player_props()

    print("\n🎯 NFL Player Prop Edges")
    build_nfl_player_prop_edges()

    print("\n🏆 NFL Rankings / Best Bets")
    build_nfl_rankings()

    print("\n✅ Alpha Wagerz full update complete.")

if __name__ == "__main__":
    run_full_update()
