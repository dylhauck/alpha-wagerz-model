from google_sheets.slate_summary_writer import update_slate_summary
from google_sheets.hitters_writer import update_hitter_matchups
from google_sheets.pitcher_slate_writer import update_pitcher_slate
from google_sheets.model_breakdown_writer import update_model_breakdown


def update_selected_game_sheets(game_id):
    update_slate_summary(game_id)
    update_hitter_matchups(game_id)
    update_pitcher_slate(game_id)
    update_model_breakdown(game_id)

    print(f"✅ Updated all selected-game sheets for game_id {game_id}")