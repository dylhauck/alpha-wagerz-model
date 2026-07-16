from __future__ import annotations

from pathlib import Path

import model.attach_hitter_metrics as hitter_metrics_module
import model.attach_pitcher_metrics as pitcher_metrics_module
import model.attach_pitch_type_matchups as pitch_type_module
import model.enrich_players as enrich_players_module


TOMORROW_GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)


def configure_tomorrow_directories():
    """
    Point the existing metric attachment modules at tomorrow's
    isolated game directory.

    The shared metric CSV files remain under data/processed because
    player performance data is the same for today and tomorrow.
    """

    hitter_metrics_module.GAMES_DIR = (
        TOMORROW_GAMES_DIR
    )

    pitcher_metrics_module.GAMES_DIR = (
        TOMORROW_GAMES_DIR
    )

    pitch_type_module.GAMES_DIR = (
        TOMORROW_GAMES_DIR
    )

    enrich_players_module.GAMES_DIR = (
        TOMORROW_GAMES_DIR
    )


def validate_tomorrow_games_directory():
    if not TOMORROW_GAMES_DIR.exists():
        raise FileNotFoundError(
            "Tomorrow game directory was not found: "
            f"{TOMORROW_GAMES_DIR}"
        )

    game_files = list(
        TOMORROW_GAMES_DIR.glob("*.json")
    )

    if not game_files:
        raise RuntimeError(
            "No tomorrow game files were found in "
            f"{TOMORROW_GAMES_DIR}"
        )

    return game_files


def attach_tomorrow_player_metrics():
    configure_tomorrow_directories()

    game_files = (
        validate_tomorrow_games_directory()
    )

    print()
    print(
        "🧬 Attaching player data to "
        f"{len(game_files)} tomorrow games"
    )

    # First enrich the raw roster/lineup players with
    # handedness, position, team and reference information.
    print()
    print("👤 Enriching tomorrow players")
    enrich_players_module.enrich_players_in_games()

    # First hitter pass:
    # Adds the shared Statcast metrics and initial Alpha scores.
    print()
    print("💥 Attaching tomorrow hitter metrics")
    hitter_metrics_module.attach_hitter_metrics_to_games()

    # Build probable-pitcher objects and pitcher scores.
    # This uses the hitter metrics from the first hitter pass.
    print()
    print("⚾ Attaching tomorrow pitcher metrics")
    pitcher_metrics_module.attach_pitcher_metrics_to_games()

    # Add pitch-arsenal and pitch-type matchup information.
    # This requires the pitcher objects created above.
    print()
    print(
        "🎯 Attaching tomorrow pitch-type matchups"
    )
    pitch_type_module.attach_pitch_type_matchups()

    # Run hitter metrics again so Alpha scores include:
    # - probable pitcher metrics
    # - pitch-type matchups
    # - arsenal scores
    #
    # attach_hitter_metrics preserves existing pitch-type fields.
    print()
    print(
        "🐺 Recalculating tomorrow hitter scores"
    )
    hitter_metrics_module.attach_hitter_metrics_to_games()

    # Final enrichment pass preserves player reference fields
    # after the hitter and pitcher objects were reformatted.
    print()
    print("👤 Final tomorrow player enrichment")
    enrich_players_module.enrich_players_in_games()

    print()
    print(
        "✅ Tomorrow player metrics attached"
    )
    print(f"📁 {TOMORROW_GAMES_DIR}")

    return len(game_files)


if __name__ == "__main__":
    attach_tomorrow_player_metrics()