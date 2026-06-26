from model.game_selector import get_game_by_id


def build_dashboard_payload(game_id):
    game = get_game_by_id(game_id)

    return {
        "selected_game": {
            "game_id": game["game_id"],
            "game": game["game"],
            "venue": game["venue"],
            "away_team": game["away_team"],
            "home_team": game["home_team"],
            "away_sp": game["away_sp"],
            "home_sp": game["home_sp"],
            "status": game["status"],
            "lineup_status": game.get("lineup_status", ""),
        },
        "slate_summary": game["slate_summary"],
        "hitters": game.get("hitters", {"away": [], "home": []}),
        "pitchers": game.get("pitchers", []),
        "weather": game.get("weather", {}),
    }