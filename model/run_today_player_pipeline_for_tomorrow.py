from __future__ import annotations

from pathlib import Path

import model.enrich_players as enrich_players_module
import model.attach_hitter_metrics as hitter_metrics_module
import model.attach_pitcher_metrics as pitcher_metrics_module
import model.attach_pitch_type_matchups as pitch_type_module


TOMORROW_GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)


def run_today_player_pipeline_for_tomorrow():
    if not TOMORROW_GAMES_DIR.exists():
        raise FileNotFoundError(
            f"Tomorrow games directory was not found: "
            f"{TOMORROW_GAMES_DIR}"
        )

    enrich_players_module.GAMES_DIR = (
        TOMORROW_GAMES_DIR
    )

    hitter_metrics_module.GAMES_DIR = (
        TOMORROW_GAMES_DIR
    )

    pitcher_metrics_module.GAMES_DIR = (
        TOMORROW_GAMES_DIR
    )

    pitch_type_module.GAMES_DIR = (
        TOMORROW_GAMES_DIR
    )

    print()
    print("👤 Enriching tomorrow players")
    enrich_players_module.enrich_players_in_games()

    print()
    print("💥 Attaching tomorrow hitter metrics")
    hitter_metrics_module.attach_hitter_metrics_to_games()

    print()
    print("⚾ Attaching tomorrow pitcher metrics")
    pitcher_metrics_module.attach_pitcher_metrics_to_games()

    print()
    print("🎯 Attaching tomorrow pitch matchups")
    pitch_type_module.attach_pitch_type_matchups()

    print()
    print("🐺 Recalculating tomorrow hitter scores")
    hitter_metrics_module.attach_hitter_metrics_to_games()

    print()
    print("👤 Final tomorrow enrichment")
    enrich_players_module.enrich_players_in_games()

    print()
    print("✅ Today player pipeline completed for tomorrow")


if __name__ == "__main__":
    run_today_player_pipeline_for_tomorrow()