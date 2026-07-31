from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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

from providers.lineups_tomorrow import (
    build_tomorrow_lineups,
)

from model.attach_lineups_tomorrow import (
    attach_tomorrow_lineups_to_games,
)
from model.normalize_tomorrow_games import (
    normalize_tomorrow_games,
)
from model.attach_tomorrow_player_metrics import (
    attach_tomorrow_player_metrics,
)
from model.fill_tomorrow_player_details import (
    fill_tomorrow_player_details,
)
from model.finalize_tomorrow_games import (
    finalize_tomorrow_games,
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


TOMORROW_GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)

TOMORROW_ALL_GAMES_FILE = Path(
    "data/tomorrow/all_games.json"
)


def load_json(
    path: Path,
    default: Any,
) -> Any:
    if not path.exists():
        return default

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_json(
    data: Any,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def game_time_sort_value(
    game: dict[str, Any],
) -> tuple[str, str]:
    return (
        str(
            game.get("game_time_sort")
            or "99:99"
        ),
        str(
            game.get("game")
            or ""
        ),
    )


def refresh_tomorrow_all_games() -> int:
    """
    Rebuild data/tomorrow/all_games.json from the final corrected
    processed game files.

    This preserves metrics, handedness, player IDs, lineups,
    pitcher data, and all other finalized fields.
    """

    if not TOMORROW_GAMES_DIR.exists():
        raise FileNotFoundError(
            "Tomorrow processed games folder was not found: "
            f"{TOMORROW_GAMES_DIR}"
        )

    games: list[dict[str, Any]] = []

    for game_file in TOMORROW_GAMES_DIR.glob(
        "*.json"
    ):
        game = load_json(
            game_file,
            default={},
        )

        if not isinstance(game, dict):
            continue

        if not game:
            continue

        games.append(game)

    games.sort(
        key=game_time_sort_value,
    )

    save_json(
        games,
        TOMORROW_ALL_GAMES_FILE,
    )

    hitter_count = 0
    hitter_hands = 0
    pitcher_count = 0
    pitcher_hands = 0

    for game in games:
        hitters = game.get("hitters", {})

        if isinstance(hitters, dict):
            away_hitters = hitters.get(
                "away",
                [],
            )
            home_hitters = hitters.get(
                "home",
                [],
            )
        else:
            away_hitters = game.get(
                "away_hitters",
                [],
            )
            home_hitters = game.get(
                "home_hitters",
                [],
            )

        if not isinstance(away_hitters, list):
            away_hitters = []

        if not isinstance(home_hitters, list):
            home_hitters = []

        all_hitters = (
            away_hitters
            + home_hitters
        )

        hitter_count += len(all_hitters)

        hitter_hands += sum(
            1
            for hitter in all_hitters
            if isinstance(hitter, dict)
            and (
                hitter.get("Bats")
                or hitter.get("bats")
            )
        )

        pitchers = game.get(
            "pitchers",
            [],
        )

        if not isinstance(pitchers, list):
            pitchers = []

        pitcher_count += len(pitchers)

        pitcher_hands += sum(
            1
            for pitcher in pitchers
            if isinstance(pitcher, dict)
            and (
                pitcher.get("Throws")
                or pitcher.get("throws")
            )
        )

    print(
        f"✅ Refreshed tomorrow all_games with "
        f"{len(games)} games"
    )

    print(
        f"   Hitter hands: "
        f"{hitter_hands}/{hitter_count}"
    )

    print(
        f"   Pitcher hands: "
        f"{pitcher_hands}/{pitcher_count}"
    )

    print(
        f"📁 {TOMORROW_ALL_GAMES_FILE}"
    )

    return len(games)


def run_tomorrow_update():
    print()
    print(
        "🌙 Starting tomorrow's slate update..."
    )

    print()
    print("🗓️ Tomorrow schedule")

    games = build_tomorrow_slate()

    if not games:
        print(
            "ℹ️ No MLB games were returned "
            "for tomorrow."
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
    print("🧹 Normalizing tomorrow games")

    normalize_tomorrow_games()

    print()
    print(
        "🧬 Attaching tomorrow player metrics"
    )

    attach_tomorrow_player_metrics()

    print()
    print("✅ Finalizing tomorrow players")

    finalize_tomorrow_games()

    print()
    print(
        "🖐️ Filling final tomorrow handedness"
    )

    fill_tomorrow_player_details()

    print()
    print(
        "📦 Refreshing tomorrow all_games"
    )

    refresh_tomorrow_all_games()

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
    print(
        "🌐 Publishing tomorrow web data"
    )

    publish_tomorrow_to_web()

    print()
    print(
        "✅ Tomorrow's slate update complete."
    )


if __name__ == "__main__":
    run_tomorrow_update()