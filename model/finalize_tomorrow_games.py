from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json

import model.attach_hitter_metrics as hitter_metrics_module
import model.attach_pitcher_metrics as pitcher_metrics_module
import model.attach_pitch_type_matchups as pitch_type_module
import model.enrich_players as enrich_players_module


TOMORROW_GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)

TOMORROW_LINEUPS_FILE = Path(
    "data/tomorrow/lineups.json"
)

TOMORROW_ALL_GAMES_FILE = Path(
    "data/tomorrow/all_games.json"
)


def clean_id(value: Any) -> str:
    return str(value or "").strip()


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_raw_hitter(
    hitter: dict[str, Any],
    team_name: str,
    team_id: Any,
) -> dict[str, Any]:
    normalized = dict(hitter)

    player_name = (
        clean_text(normalized.get("Player"))
        or clean_text(normalized.get("name"))
        or clean_text(normalized.get("player_name"))
    )

    player_id = (
        normalized.get("Player ID")
        or normalized.get("player_id")
        or normalized.get("id")
    )

    position = (
        clean_text(normalized.get("Position"))
        or clean_text(normalized.get("position"))
    )

    normalized["Player"] = player_name
    normalized["name"] = player_name
    normalized["player_name"] = player_name

    normalized["Player ID"] = player_id
    normalized["player_id"] = player_id
    normalized["id"] = player_id

    normalized["Team"] = (
        clean_text(normalized.get("Team"))
        or clean_text(normalized.get("team"))
        or team_name
    )

    normalized["team"] = normalized["Team"]

    normalized["Team ID"] = (
        normalized.get("Team ID")
        or normalized.get("team_id")
        or team_id
    )

    normalized["team_id"] = normalized["Team ID"]

    normalized["Position"] = position
    normalized["position"] = position

    return normalized


def get_lineup_lookup() -> dict[str, dict[str, Any]]:
    rows = load_json(
        TOMORROW_LINEUPS_FILE,
        default=[],
    )

    if not isinstance(rows, list):
        raise ValueError(
            f"Expected a list in "
            f"{TOMORROW_LINEUPS_FILE}"
        )

    lookup: dict[str, dict[str, Any]] = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        game_id = clean_id(
            row.get("game_id")
        )

        if game_id:
            lookup[game_id] = row

    return lookup


def configure_shared_modules() -> None:
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


def force_lineups_into_game_files() -> int:
    lineup_lookup = get_lineup_lookup()

    updated = 0

    for game_file in TOMORROW_GAMES_DIR.glob(
        "*.json"
    ):
        game = load_json(
            game_file,
            default={},
        )

        if not isinstance(game, dict) or not game:
            continue

        game_id = clean_id(
            game.get("game_id")
        )

        lineup = lineup_lookup.get(
            game_id,
            {},
        )

        if not lineup:
            print(
                f"⚠️ No lineup row found for "
                f"{game.get('game', game_id)}"
            )
            continue

        away_team = (
            clean_text(lineup.get("away_team"))
            or clean_text(game.get("away_team"))
        )

        home_team = (
            clean_text(lineup.get("home_team"))
            or clean_text(game.get("home_team"))
        )

        away_team_id = (
            lineup.get("away_team_id")
            or game.get("away_team_id")
        )

        home_team_id = (
            lineup.get("home_team_id")
            or game.get("home_team_id")
        )

        raw_away_hitters = lineup.get(
            "away_hitters",
            [],
        )

        raw_home_hitters = lineup.get(
            "home_hitters",
            [],
        )

        if not isinstance(raw_away_hitters, list):
            raw_away_hitters = []

        if not isinstance(raw_home_hitters, list):
            raw_home_hitters = []

        away_hitters = [
            normalize_raw_hitter(
                hitter,
                away_team,
                away_team_id,
            )
            for hitter in raw_away_hitters
            if isinstance(hitter, dict)
        ]

        home_hitters = [
            normalize_raw_hitter(
                hitter,
                home_team,
                home_team_id,
            )
            for hitter in raw_home_hitters
            if isinstance(hitter, dict)
        ]

        game["away_team"] = away_team
        game["home_team"] = home_team

        game["away_team_id"] = away_team_id
        game["home_team_id"] = home_team_id

        game["away_sp"] = (
            clean_text(lineup.get("away_sp"))
            or clean_text(game.get("away_sp"))
        )

        game["home_sp"] = (
            clean_text(lineup.get("home_sp"))
            or clean_text(game.get("home_sp"))
        )

        game["away_sp_id"] = (
            lineup.get("away_sp_id")
            or game.get("away_sp_id")
        )

        game["home_sp_id"] = (
            lineup.get("home_sp_id")
            or game.get("home_sp_id")
        )

        game["away_pitcher_id"] = (
            game.get("away_sp_id")
        )

        game["home_pitcher_id"] = (
            game.get("home_sp_id")
        )

        game["lineup_status"] = lineup.get(
            "lineup_status",
            "roster_fallback",
        )

        game["away_lineup_status"] = (
            lineup.get(
                "away_lineup_status",
                "roster_fallback",
            )
        )

        game["home_lineup_status"] = (
            lineup.get(
                "home_lineup_status",
                "roster_fallback",
            )
        )

        game["away_hitters"] = away_hitters
        game["home_hitters"] = home_hitters

        game["hitters"] = {
            "away": away_hitters,
            "home": home_hitters,
        }

        save_json(
            game,
            game_file,
        )

        updated += 1

        print(
            f"✅ Forced lineups into "
            f"{game.get('game', game_id)} | "
            f"{len(away_hitters)} away | "
            f"{len(home_hitters)} home | "
            f"{game.get('away_sp') or 'TBD'} vs "
            f"{game.get('home_sp') or 'TBD'}"
        )

    return updated


def repair_completed_game_files() -> int:
    repaired = 0

    for game_file in TOMORROW_GAMES_DIR.glob(
        "*.json"
    ):
        game = load_json(
            game_file,
            default={},
        )

        if not isinstance(game, dict) or not game:
            continue

        hitters = game.get("hitters")

        if not isinstance(hitters, dict):
            hitters = {}

        away_hitters = hitters.get("away")

        if not isinstance(away_hitters, list):
            away_hitters = game.get(
                "away_hitters",
                [],
            )

        home_hitters = hitters.get("home")

        if not isinstance(home_hitters, list):
            home_hitters = game.get(
                "home_hitters",
                [],
            )

        if not isinstance(away_hitters, list):
            away_hitters = []

        if not isinstance(home_hitters, list):
            home_hitters = []

        game["away_hitters"] = away_hitters
        game["home_hitters"] = home_hitters

        game["hitters"] = {
            "away": away_hitters,
            "home": home_hitters,
        }

        pitchers = game.get("pitchers")

        if not isinstance(pitchers, list):
            pitchers = []

        game["pitchers"] = pitchers

        game["away_pitcher"] = (
            pitchers[0]
            if len(pitchers) >= 1
            else {}
        )

        game["home_pitcher"] = (
            pitchers[1]
            if len(pitchers) >= 2
            else {}
        )

        save_json(
            game,
            game_file,
        )

        repaired += 1

        print(
            f"✅ Repaired {game.get('game')} | "
            f"{len(away_hitters)} away hitters | "
            f"{len(home_hitters)} home hitters | "
            f"{len(pitchers)} pitchers"
        )

    return repaired


def build_final_tomorrow_all_games() -> list[
    dict[str, Any]
]:
    games: list[dict[str, Any]] = []

    for game_file in TOMORROW_GAMES_DIR.glob(
        "*.json"
    ):
        game = load_json(
            game_file,
            default={},
        )

        if isinstance(game, dict) and game:
            games.append(game)

    games.sort(
        key=lambda game: (
            clean_text(
                game.get("game_time_sort")
            ),
            clean_text(game.get("game")),
        )
    )

    save_json(
        games,
        TOMORROW_ALL_GAMES_FILE,
    )

    print()
    print(
        f"✅ Built final tomorrow all_games "
        f"with {len(games)} games"
    )
    print(f"📁 {TOMORROW_ALL_GAMES_FILE}")

    return games


def finalize_tomorrow_games():
    if not TOMORROW_GAMES_DIR.exists():
        raise FileNotFoundError(
            f"Missing tomorrow game directory: "
            f"{TOMORROW_GAMES_DIR}"
        )

    print()
    print("📋 Restoring tomorrow lineups")

    forced = force_lineups_into_game_files()

    if forced == 0:
        raise RuntimeError(
            "No tomorrow lineups were attached. "
            "Check data/tomorrow/lineups.json."
        )

    configure_shared_modules()

    print()
    print("👤 Enriching tomorrow roster players")
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
    print("🐺 Recalculating tomorrow hitter model")
    hitter_metrics_module.attach_hitter_metrics_to_games()

    print()
    print("🧹 Repairing final tomorrow structure")
    repair_completed_game_files()

    games = build_final_tomorrow_all_games()

    print()
    print("✅ Tomorrow games fully finalized")

    return games


if __name__ == "__main__":
    finalize_tomorrow_games()