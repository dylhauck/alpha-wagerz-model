from __future__ import annotations

from providers.mlb_tomorrow import (
    build_tomorrow_slate,
)
from providers.weather_tomorrow import (
    build_tomorrow_weather_file,
)
from providers.market_tomorrow import (
    build_tomorrow_market_lines,
)

from scripts.build_tomorrow_game_files import (
    build_tomorrow_game_files,
)
from scripts.build_tomorrow_game_index import (
    build_tomorrow_game_index,
)

from model.attach_weather_tomorrow import (
    attach_tomorrow_weather_to_games,
)
from model.attach_market_tomorrow import (
    attach_tomorrow_market_to_games,
)
from model.rankings_tomorrow import (
    build_tomorrow_rankings,
)
from model.export_game_projections_tomorrow import (
    export_tomorrow_game_projections,
)
from model.publish_tomorrow_to_web import (
    publish_tomorrow_to_web,
)

from providers.lineups_tomorrow import (
    build_tomorrow_lineups,
)

from model.attach_lineups_tomorrow import (
    attach_tomorrow_lineups_to_games,
)

from model.attach_tomorrow_player_metrics import (
    attach_tomorrow_player_metrics,
)

from model.normalize_tomorrow_games import (
    normalize_tomorrow_games,
)

from model.finalize_tomorrow_games import (
    finalize_tomorrow_games,
    build_final_tomorrow_all_games,
)

from model.fill_tomorrow_player_details import (
    fill_tomorrow_player_details,
)


def run_tomorrow_update():
    print()
    print("🌙 Starting tomorrow's slate update...")

    print()
    print("🗓️ Tomorrow schedule")
    games = build_tomorrow_slate()

    if not games:
        print(
            "ℹ️ No MLB games were returned for tomorrow."
        )
        return

    print()
    print("📂 Tomorrow game files")
    build_tomorrow_game_files()
    build_tomorrow_game_index()

    print()
    print("📋 Tomorrow lineups")
    build_tomorrow_lineups()
    attach_tomorrow_lineups_to_games()

    print()
    print("🧬 Finalizing tomorrow players")
    finalize_tomorrow_games()

    print()
    print("🤚 Filling tomorrow handedness")
    fill_tomorrow_player_details()

    # Rebuild all_games.json from the completed individual
    # game files. This preserves hitters, pitchers, metrics,
    # Bats, Throws, and Game values.
    print()
    print("📦 Updating tomorrow all-games data")
    build_final_tomorrow_all_games()

    print()
    print("🌤️ Tomorrow weather")
    build_tomorrow_weather_file()
    attach_tomorrow_weather_to_games()

    print()
    print("💰 Tomorrow market lines")
    build_tomorrow_market_lines()
    attach_tomorrow_market_to_games()

    print()
    print("🏆 Tomorrow outputs")
    build_tomorrow_rankings()
    export_tomorrow_game_projections()

    print()
    print("🌐 Publishing tomorrow web data")
    publish_tomorrow_to_web()

    print()
    print("✅ Tomorrow's slate update complete.")


if __name__ == "__main__":
    run_tomorrow_update()