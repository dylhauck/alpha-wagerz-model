from google_sheets.rankings_writer import update_rankings_sheet
from google_sheets.weather_writer import update_weather_sheet
from google_sheets.all_games_writer import update_all_games_sheet
from google_sheets.full_slate_hitters_writer import update_full_slate_hitters_sheet
from google_sheets.full_slate_pitchers_writer import update_full_slate_pitchers_sheet


def update_full_slate_sheets():
    update_rankings_sheet()
    update_weather_sheet()
    update_all_games_sheet()
    update_full_slate_hitters_sheet()
    update_full_slate_pitchers_sheet()

    print("✅ Updated all full-slate sheets")