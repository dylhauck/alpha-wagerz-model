from time import perf_counter

from graphics.create_weather_graphic import create_weather_graphic
from model.nfl.injury_context import build_nfl_injury_context
from providers.mlb.mlb_reference import build_reference_files
from providers.mlb.mlb_players import build_player_reference
from providers.mlb.statcast import (
    get_statcast_batter_events,
    get_statcast_season_events,
    get_statcast_longterm_events,
)
from providers.mlb.weather import build_weather_file
from providers.mlb.pitch_mix import build_pitch_mix
from scripts.mlb.update_today import main as update_today
from model.mlb.attach_weather import attach_weather_to_games
from model.mlb.hitter_metrics import build_hitter_metrics
from model.mlb.pitcher_metrics import build_pitcher_metrics
from model.mlb.hitter_pitch_type_metrics import build_hitter_pitch_type_metrics
from model.mlb.attach_pitcher_metrics import attach_pitcher_metrics_to_games
from model.mlb.attach_pitch_type_matchups import attach_pitch_type_matchups
from model.mlb.attach_hitter_metrics import attach_hitter_metrics_to_games
from model.mlb.enrich_players import enrich_players_in_games
from model.mlb.rankings import build_rankings
from model.mlb.build_all_games import build_all_games
from model.mlb.validate_pipeline import validate_pipeline
from model.mlb.team_offense_metrics import build_team_offense_metrics
from model.mlb.attach_team_context import attach_team_context
from google_sheets.update_full_slate import update_full_slate_sheets
from model.mlb.bullpen_metrics import build_bullpen_metrics
from model.mlb.attach_bullpen_context import attach_bullpen_context
from model.mlb.validate_model_features import validate_model_features
from model.mlb.pitch_arsenal_metrics import build_pitch_arsenal_metrics
from model.mlb.zone_allowed_metrics import build_zone_allowed_metrics
from model.mlb.save_history import save_daily_history
from model.mlb.publish_to_web import publish_to_web
from providers.mlb.standings import build_team_context_file
from model.mlb.attach_team_standings import attach_team_standings
from model.mlb.attach_game_times import attach_game_times
from model.mlb.export_hr_graphic_data import export_hr_graphic_data
from graphics.create_hr_targets_graphic import create_graphic
from model.mlb.export_game_projections import export_game_projections
from providers.mlb.market import build_market_lines
from providers.mlb.espn_injuries import build_injury_report
from pipeline.tomorrow_update import run_tomorrow_update

# NFL
from providers.nfl.nfl_data import build_all_nfl_data
from providers.nfl.nfl_matchups import build_nfl_matchups
from providers.nfl.nfl_injuries import build_nfl_injuries
from providers.nfl.nfl_weather import build_nfl_weather
from providers.nfl.nfl_market import build_nfl_market
from model.nfl.team_metrics import build_team_metrics
from model.nfl.player_metrics import build_nfl_player_metrics
from model.nfl.matchup_metrics import build_nfl_matchup_metrics
from model.nfl.game_projections import build_nfl_game_projections
from model.nfl.player_projections import build_nfl_player_projections
from model.nfl.edge_engine import build_nfl_edges
from providers.nfl.nfl_player_props import build_nfl_player_props
from model.nfl.player_prop_edges import build_nfl_player_prop_edges
from providers.nfl.nfl_odds import build_nfl_odds
from model.nfl.rankings import build_nfl_rankings
# NBA
from providers.nba.nba_data import build_nba_data
from providers.nba.nba_players import main as build_nba_players
from model.nba.team_rankings import build_nba_team_rankings
from model.nba.player_matchups import main as build_nba_player_matchups


def format_duration(seconds):
    minutes, seconds = divmod(seconds, 60)
    return f"{int(minutes)}m {seconds:.2f}s" if minutes >= 1 else f"{seconds:.2f}s"


def timed(label, func, *args, **kwargs):
    start = perf_counter()
    try:
        return func(*args, **kwargs)
    finally:
        print(f"⏱️ {label}: {format_duration(perf_counter() - start)}", flush=True)


def run_full_update():
    pipeline_start = perf_counter()
    print("🐺 Starting Alpha Wagerz full update...", flush=True)

    print("\n📚 Reference data", flush=True)
    timed("build_reference_files", build_reference_files)
    timed("build_player_reference", build_player_reference)

    print("\n🗓️ Slate / lineups", flush=True)
    timed("update_today", update_today)
    timed("build_team_context_file", build_team_context_file)

    print("\n🏥 Injury report", flush=True)
    timed("build_injury_report", build_injury_report)

    print("\n📊 Statcast", flush=True)
    print("\n📊 Pulling Last 30 Days Statcast...", flush=True)
    timed("get_statcast_batter_events", get_statcast_batter_events)
    print("\n📊 Pulling Current Season Statcast...", flush=True)
    timed("get_statcast_season_events", get_statcast_season_events)
    print("\n📊 Pulling Long-Term Statcast...", flush=True)
    timed("get_statcast_longterm_events", get_statcast_longterm_events)

    print("\n🌤️ Weather", flush=True)
    timed("build_weather_file", build_weather_file)

    print("\n⚾ Metrics", flush=True)
    timed("build_hitter_metrics", build_hitter_metrics)
    timed("build_pitcher_metrics", build_pitcher_metrics)
    timed("build_pitch_mix", build_pitch_mix)
    timed("build_hitter_pitch_type_metrics", build_hitter_pitch_type_metrics)
    timed("build_pitch_arsenal_metrics", build_pitch_arsenal_metrics)
    timed("build_zone_allowed_metrics", build_zone_allowed_metrics)
    timed("build_team_offense_metrics", build_team_offense_metrics)
    timed("build_bullpen_metrics", build_bullpen_metrics)

    print("\n🔗 Attachments", flush=True)
    timed("attach_weather_to_games", attach_weather_to_games)
    timed("attach_team_context", attach_team_context)
    timed("attach_bullpen_context", attach_bullpen_context)
    timed("attach_team_standings", attach_team_standings)
    timed("attach_game_times", attach_game_times)
    timed("attach_hitter_metrics_to_games", attach_hitter_metrics_to_games)
    timed("attach_pitch_type_matchups", attach_pitch_type_matchups)
    timed("attach_pitcher_metrics_to_games", attach_pitcher_metrics_to_games)
    timed("enrich_players_in_games", enrich_players_in_games)

    print("\n🏗️ Building combined game data", flush=True)
    timed("build_all_games", build_all_games)

    print("\n💰 Market Lines", flush=True)
    timed("build_market_lines", build_market_lines)

    print("\n🏆 Outputs", flush=True)
    timed("build_rankings", build_rankings)
    timed("export_game_projections", export_game_projections)
    timed("export_hr_graphic_data", export_hr_graphic_data)
    timed("create_graphic", create_graphic)
    timed("create_weather_graphic", create_weather_graphic)

    print("\n🔎 Validation", flush=True)
    timed("validate_pipeline", validate_pipeline)
    timed("validate_model_features", validate_model_features)

    print("\n🌐 Publishing web data", flush=True)
    timed("publish_to_web", publish_to_web)

    print("\n🌙 Tomorrow's Slate", flush=True)
    timed("run_tomorrow_update", run_tomorrow_update)

    print("\n📄 Google Sheets", flush=True)
    timed("update_full_slate_sheets", update_full_slate_sheets)

    print("\n🗄️ Saving history", flush=True)
    timed("save_daily_history", save_daily_history)

    print("\n🏈 NFL Data", flush=True)
    timed("build_all_nfl_data", build_all_nfl_data)
    print("\n🏥 NFL Injuries", flush=True)
    timed("build_nfl_injuries", build_nfl_injuries)
    print("\n📊 NFL Team Metrics", flush=True)
    timed("build_team_metrics", build_team_metrics)
    print("\n👤 NFL Player Metrics", flush=True)
    timed("build_nfl_player_metrics", build_nfl_player_metrics)
    print("\n⚔️ NFL Matchup History", flush=True)
    timed("build_nfl_matchups", build_nfl_matchups)
    print("\n🧠 NFL Matchup Metrics", flush=True)
    timed("build_nfl_matchup_metrics", build_nfl_matchup_metrics)
    print("\n🏥 NFL Injury Context", flush=True)
    timed("build_nfl_injury_context", build_nfl_injury_context)
    print("\n🌦️ NFL Weather", flush=True)
    timed("build_nfl_weather", build_nfl_weather)
    print("\n🎯 NFL Game Projections", flush=True)
    timed("build_nfl_game_projections", build_nfl_game_projections)
    print("\n🏃 NFL Player Projections", flush=True)
    timed("build_nfl_player_projections", build_nfl_player_projections)
    print("\n📡 Live NFL Odds", flush=True)
    timed("build_nfl_odds", build_nfl_odds)
    print("\n💰 NFL Market", flush=True)
    timed("build_nfl_market", build_nfl_market)
    print("\n📈 NFL Edges & Confidence", flush=True)
    timed("build_nfl_edges", build_nfl_edges)
    print("\n🏷️ NFL Player Props", flush=True)
    timed("build_nfl_player_props", build_nfl_player_props)
    print("\n🎯 NFL Player Prop Edges", flush=True)
    timed("build_nfl_player_prop_edges", build_nfl_player_prop_edges)
    print("\n🏆 NFL Rankings / Best Bets", flush=True)
    timed("build_nfl_rankings", build_nfl_rankings)

    # NBA
    print("\nNBA Data", flush=True)
    timed("build_nba_data", build_nba_data)

    print("\nNBA Players", flush=True)
    timed("build_nba_players", build_nba_players)

    print("\nNBA Team Rankings", flush=True)
    timed("build_nba_team_rankings", build_nba_team_rankings)

    print("\nNBA Player Matchups", flush=True)
    timed("build_nba_player_matchups", build_nba_player_matchups)

    print("\n✅ Alpha Wagerz full update complete.", flush=True)
    print(f"⏱️ TOTAL FULL UPDATE: {format_duration(perf_counter() - pipeline_start)}", flush=True)


if __name__ == "__main__":
    run_full_update()

