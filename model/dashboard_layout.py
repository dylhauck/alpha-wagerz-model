def build_dashboard_rows(payload, game_tabs):
    selected = payload["selected_game"]
    summary = payload.get("slate_summary", {})
    weather = payload.get("weather", {})

    rows = [
        ["ALPHA WAGERZ MLB MODEL"],
        [],
        ["GAME TABS"],
        game_tabs,
        [],
        ["SELECTED GAME SUMMARY"],
        ["Game", selected.get("game", "")],
        ["Venue", selected.get("venue", "")],
        ["Weather", weather.get("conditions", "")],
        ["Wind", weather.get("wind", "")],
        ["Away SP", selected.get("away_sp", "")],
        ["Home SP", selected.get("home_sp", "")],
        ["Lineup Status", selected.get("lineup_status", "")],
        [],
        ["ALPHA GAME PREDICTIONS"],
        ["Moneyline Lean", summary.get("moneyline_lean", "")],
        ["Run Line / Spread Lean", summary.get("spread_lean", "")],
        ["Over/Under Lean", summary.get("total_lean", "")],
        ["Projected Score", summary.get("projected_score", "")],
        ["Confidence Score", summary.get("confidence_score", "")],
        [],
        ["GAME ENVIRONMENT"],
        ["Weather Boost", summary.get("weather_boost", "")],
        ["Park Factor", summary.get("park_factor", "")],
        ["Offensive Rating", summary.get("offensive_rating", "")],
        ["Pitching Risk", summary.get("pitching_risk", "")],
        ["Bullpen Risk", summary.get("bullpen_risk", "")],
        [],
        ["KEY NOTES"],
        ["Best HR Environment", summary.get("best_hr_environment", "")],
        ["Better Side For Power", summary.get("better_side_for_power", "")],
        ["Pitcher Advantage", summary.get("pitcher_advantage", "")],
        ["Lineup Watch", summary.get("lineup_watch", "")],
    ]

    return rows