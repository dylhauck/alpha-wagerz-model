from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import playergamelogs


# ============================================================
# PATHS
# ============================================================

MODEL_ROOT = Path(__file__).resolve().parents[2]

NBA_DIR = MODEL_ROOT / "data" / "processed" / "nba"

WEB_NBA_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nba"
)

PLAYERS_FILE = NBA_DIR / "players.json"

OUTPUT_FILE = NBA_DIR / "player_stats.json"
HISTORY_FILE = NBA_DIR / "player_stats_history.json"

WEB_OUTPUT_FILE = WEB_NBA_DIR / "player_stats.json"
WEB_HISTORY_FILE = WEB_NBA_DIR / "player_stats_history.json"



# ============================================================
# SEASONS
# ============================================================

CURRENT_SEASON = "2026-27"
LAST_SEASON = "2025-26"

SEASON_TYPE = "Regular Season"

REQUEST_TIMEOUT = 30
MAX_RETRIES = 3
REQUEST_DELAY_SECONDS = 1.0


# ============================================================
# HELPERS
# ============================================================

def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected JSON object in {path}"
        )

    return payload


def write_json(
    path: Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )


def clean_text(value: Any) -> str:
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    return str(value).strip()


def safe_float(value: Any) -> float:
    try:
        if value is None or pd.isna(value):
            return 0.0

        number = float(value)

        if not math.isfinite(number):
            return 0.0

        return number

    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        if value is None or pd.isna(value):
            return 0

        return int(float(value))

    except (TypeError, ValueError):
        return 0


def round_stat(
    value: float,
    digits: int = 1,
) -> float:
    return round(
        float(value),
        digits,
    )


def pct(
    made: float,
    attempted: float,
) -> float:
    if attempted <= 0:
        return 0.0

    return round(
        made / attempted,
        3,
    )


# ============================================================
# PLAYER REFERENCE
# ============================================================

def build_player_reference(
    payload: dict[str, Any],
) -> dict[int, dict[str, Any]]:
    players = payload.get("players", [])

    if not isinstance(players, list) or not players:
        raise ValueError(
            f"No players found in {PLAYERS_FILE}"
        )

    by_id: dict[int, dict[str, Any]] = {}

    for player in players:
        if not isinstance(player, dict):
            continue

        player_id = safe_int(
            player.get("player_id")
        )

        if player_id <= 0:
            continue

        by_id[player_id] = {
            "player_id": player_id,
            "player_name": clean_text(
                player.get("player_name")
            ),
            "team_id": safe_int(
                player.get("team_id")
            ),
            "team": clean_text(
                player.get("team")
            ).upper(),
            "team_name": clean_text(
                player.get("team_name")
            ),
            "position": (
                clean_text(
                    player.get("position")
                )
                or "N/A"
            ),
            "position_group": (
                clean_text(
                    player.get(
                        "position_group"
                    )
                )
                or "N/A"
            ),
            "number": clean_text(
                player.get("number")
            ),
        }

    if not by_id:
        raise ValueError(
            "NBA player reference contains "
            "zero valid players."
        )

    return by_id


# ============================================================
# STAT STRUCTURES
# ============================================================

def empty_totals() -> dict[str, Any]:
    return {
        "min": 0.0,
        "pts": 0,
        "reb": 0,
        "ast": 0,
        "stl": 0,
        "blk": 0,
        "tov": 0,
        "fgm": 0,
        "fga": 0,
        "fg3m": 0,
        "fg3a": 0,
        "ftm": 0,
        "fta": 0,
    }


def empty_per_game() -> dict[str, float]:
    return {
        "min": 0.0,
        "pts": 0.0,
        "reb": 0.0,
        "ast": 0.0,
        "stl": 0.0,
        "blk": 0.0,
        "tov": 0.0,
        "fg3m": 0.0,
    }


def empty_percentages() -> dict[str, float]:
    return {
        "fg_pct": 0.0,
        "fg3_pct": 0.0,
        "ft_pct": 0.0,
    }


def empty_stat_block() -> dict[str, Any]:
    return {
        "games": 0,
        "totals": empty_totals(),
        "per_game": empty_per_game(),
        "percentages": empty_percentages(),
    }


def normalize_totals(
    totals: Any,
) -> dict[str, Any]:
    base = empty_totals()

    if not isinstance(totals, dict):
        return base

    base["min"] = round_stat(
        safe_float(totals.get("min")),
        1,
    )

    for key in (
        "pts",
        "reb",
        "ast",
        "stl",
        "blk",
        "tov",
        "fgm",
        "fga",
        "fg3m",
        "fg3a",
        "ftm",
        "fta",
    ):
        base[key] = safe_int(
            totals.get(key)
        )

    return base


def build_stat_block_from_totals(
    games: int,
    totals: dict[str, Any],
) -> dict[str, Any]:
    games = max(
        safe_int(games),
        0,
    )

    normalized = normalize_totals(
        totals
    )

    if games <= 0:
        return empty_stat_block()

    per_game = {
        "min": round_stat(
            normalized["min"] / games
        ),
        "pts": round_stat(
            normalized["pts"] / games
        ),
        "reb": round_stat(
            normalized["reb"] / games
        ),
        "ast": round_stat(
            normalized["ast"] / games
        ),
        "stl": round_stat(
            normalized["stl"] / games
        ),
        "blk": round_stat(
            normalized["blk"] / games
        ),
        "tov": round_stat(
            normalized["tov"] / games
        ),
        "fg3m": round_stat(
            normalized["fg3m"] / games
        ),
    }

    percentages = {
        "fg_pct": pct(
            normalized["fgm"],
            normalized["fga"],
        ),
        "fg3_pct": pct(
            normalized["fg3m"],
            normalized["fg3a"],
        ),
        "ft_pct": pct(
            normalized["ftm"],
            normalized["fta"],
        ),
    }

    return {
        "games": games,
        "totals": normalized,
        "per_game": per_game,
        "percentages": percentages,
    }


def combine_stat_blocks(
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    first_games = safe_int(
        first.get("games")
    )

    second_games = safe_int(
        second.get("games")
    )

    first_totals = normalize_totals(
        first.get("totals")
    )

    second_totals = normalize_totals(
        second.get("totals")
    )

    combined_totals = empty_totals()

    combined_totals["min"] = round_stat(
        first_totals["min"]
        + second_totals["min"],
        1,
    )

    for key in (
        "pts",
        "reb",
        "ast",
        "stl",
        "blk",
        "tov",
        "fgm",
        "fga",
        "fg3m",
        "fg3a",
        "ftm",
        "fta",
    ):
        combined_totals[key] = (
            first_totals[key]
            + second_totals[key]
        )

    return build_stat_block_from_totals(
        games=(
            first_games
            + second_games
        ),
        totals=combined_totals,
    )


# ============================================================
# BOOTSTRAP HISTORICAL BASELINE
# ============================================================

def bootstrap_history_from_existing_stats(
    players_by_id: dict[
        int,
        dict[str, Any],
    ],
) -> dict[str, Any]:
    """
    Bootstrap the historical baseline from the full player_stats.json
    created by the initial 31-season build.

    Since 2026-27 currently has zero regular-season games, the career
    block in that file is currently equivalent to the historical
    baseline through 2025-26.
    """

    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(
            "Historical NBA player stats baseline does not exist "
            "and player_stats.json is unavailable for bootstrap."
        )

    print()
    print("=" * 70)
    print("BOOTSTRAPPING NBA PLAYER HISTORY")
    print("=" * 70)
    print()

    print(
        f"Source: {OUTPUT_FILE}"
    )

    existing = load_json(
        OUTPUT_FILE
    )

    existing_players = existing.get(
        "players",
        [],
    )

    if (
        not isinstance(existing_players, list)
        or not existing_players
    ):
        raise ValueError(
            "Existing player_stats.json cannot be used "
            "to bootstrap historical stats."
        )

    by_id: dict[int, dict[str, Any]] = {}

    for player in existing_players:
        if not isinstance(player, dict):
            continue

        player_id = safe_int(
            player.get("player_id")
        )

        if player_id <= 0:
            continue

        current_block = player.get(
            "current_season",
            {},
        )

        current_games = safe_int(
            current_block.get("games")
            if isinstance(
                current_block,
                dict,
            )
            else 0
        )

        if current_games > 0:
            raise RuntimeError(
                "Cannot automatically bootstrap historical "
                "baseline because player_stats.json already "
                "contains current-season games. Historical "
                "baseline must be rebuilt separately."
            )

        career = player.get(
            "career",
            {},
        )

        last_season = player.get(
            "last_season",
            {},
        )

        if not isinstance(career, dict):
            career = {}

        if not isinstance(
            last_season,
            dict,
        ):
            last_season = {}

        career_block = (
            build_stat_block_from_totals(
                games=safe_int(
                    career.get("games")
                ),
                totals=normalize_totals(
                    career.get("totals")
                ),
            )
        )

        last_season_block = (
            build_stat_block_from_totals(
                games=safe_int(
                    last_season.get("games")
                ),
                totals=normalize_totals(
                    last_season.get("totals")
                ),
            )
        )

        seasons = career.get(
            "seasons",
            [],
        )

        if not isinstance(seasons, list):
            seasons = []

        seasons = [
            clean_text(season)
            for season in seasons
            if clean_text(season)
            and clean_text(season)
            != CURRENT_SEASON
        ]

        by_id[player_id] = {
            "career_through_last_season": {
                "seasons": seasons,
                "season_count": len(
                    seasons
                ),
                **career_block,
            },
            "last_season": {
                "season": LAST_SEASON,
                **last_season_block,
            },
        }

    historical_players = 0

    for player_id in players_by_id:
        record = by_id.get(
            player_id
        )

        if (
            record
            and record[
                "career_through_last_season"
            ]["games"] > 0
        ):
            historical_players += 1

    payload = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "league": "NBA",
        "season_type": SEASON_TYPE,
        "through_season": LAST_SEASON,
        "current_season_excluded": (
            CURRENT_SEASON
        ),
        "player_count": len(by_id),
        "players_with_history": (
            historical_players
        ),
        "players": {
            str(player_id): data
            for player_id, data
            in by_id.items()
        },
    }

    write_json(
        HISTORY_FILE,
        payload,
    )

    write_json(
        WEB_HISTORY_FILE,
        payload,
    )

    print(
        f"Historical baseline saved: "
        f"{HISTORY_FILE}"
    )

    print(
        f"Web historical baseline: "
        f"{WEB_HISTORY_FILE}"
    )
    
    print(
        f"Players in baseline: "
        f"{len(by_id):,}"
    )
    print(
        f"Players with history: "
        f"{historical_players:,}"
    )

    return payload


def load_or_create_history(
    players_by_id: dict[
        int,
        dict[str, Any],
    ],
) -> dict[str, Any]:
    if not HISTORY_FILE.exists():
        return (
            bootstrap_history_from_existing_stats(
                players_by_id
            )
        )

    payload = load_json(
        HISTORY_FILE
    )

    if (
        clean_text(
            payload.get("through_season")
        )
        != LAST_SEASON
    ):
        raise RuntimeError(
            "NBA historical player baseline is for "
            f"{payload.get('through_season')}, "
            f"but this build expects {LAST_SEASON}."
        )

    players = payload.get(
        "players"
    )

    if not isinstance(players, dict):
        raise ValueError(
            "NBA historical player baseline "
            "is invalid."
        )

    return payload


# ============================================================
# CURRENT-SEASON NBA API
# ============================================================

def fetch_current_season_game_logs() -> pd.DataFrame:
    last_error: Exception | None = None

    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            print(
                f"Fetching {CURRENT_SEASON} "
                f"player game logs "
                f"(attempt {attempt}/{MAX_RETRIES})..."
            )

            response = (
                playergamelogs.PlayerGameLogs(
                    season_nullable=(
                        CURRENT_SEASON
                    ),
                    season_type_nullable=(
                        SEASON_TYPE
                    ),
                    league_id_nullable="00",
                    timeout=REQUEST_TIMEOUT,
                )
            )

            frames = response.get_data_frames()

            if not frames:
                print(
                    "No current-season data "
                    "frame returned."
                )
                return pd.DataFrame()

            frame = frames[0].copy()

            print(
                f"{CURRENT_SEASON}: "
                f"{len(frame):,} player-game rows"
            )

            return frame

        except Exception as exc:
            last_error = exc

            print(
                f"ERROR: "
                f"{type(exc).__name__}: {exc}"
            )

            if attempt < MAX_RETRIES:
                wait_seconds = (
                    attempt * 3
                )

                print(
                    f"Retrying in "
                    f"{wait_seconds} seconds..."
                )

                time.sleep(
                    wait_seconds
                )

    raise RuntimeError(
        f"Unable to fetch NBA player game logs "
        f"for {CURRENT_SEASON}"
    ) from last_error


# ============================================================
# CURRENT-SEASON AGGREGATION
# ============================================================

def aggregate_current_season(
    frame: pd.DataFrame,
    current_player_ids: set[int],
) -> dict[int, dict[str, Any]]:
    raw: dict[
        int,
        dict[str, Any],
    ] = {}

    if frame.empty:
        return {}

    for _, row in frame.iterrows():
        player_id = safe_int(
            row.get("PLAYER_ID")
        )

        if (
            player_id <= 0
            or player_id
            not in current_player_ids
        ):
            continue

        if player_id not in raw:
            raw[player_id] = {
                "games": 0,
                "totals": empty_totals(),
            }

        record = raw[player_id]

        record["games"] += 1

        totals = record["totals"]

        totals["min"] += safe_float(
            row.get("MIN")
        )

        for source, target in (
            ("PTS", "pts"),
            ("REB", "reb"),
            ("AST", "ast"),
            ("STL", "stl"),
            ("BLK", "blk"),
            ("TOV", "tov"),
            ("FGM", "fgm"),
            ("FGA", "fga"),
            ("FG3M", "fg3m"),
            ("FG3A", "fg3a"),
            ("FTM", "ftm"),
            ("FTA", "fta"),
        ):
            totals[target] += safe_float(
                row.get(source)
            )

    output: dict[
        int,
        dict[str, Any],
    ] = {}

    for player_id, record in raw.items():
        output[player_id] = (
            build_stat_block_from_totals(
                games=record["games"],
                totals=record["totals"],
            )
        )

    return output


# ============================================================
# BUILD FRONTEND PLAYER DATA
# ============================================================

def build_player_stats(
    players_by_id: dict[
        int,
        dict[str, Any],
    ],
    history_payload: dict[str, Any],
    current_stats: dict[
        int,
        dict[str, Any],
    ],
) -> list[dict[str, Any]]:
    history_players = (
        history_payload.get(
            "players",
            {},
        )
    )

    if not isinstance(
        history_players,
        dict,
    ):
        history_players = {}

    output: list[dict[str, Any]] = []

    for player_id, player in (
        players_by_id.items()
    ):
        history = history_players.get(
            str(player_id),
            {},
        )

        if not isinstance(history, dict):
            history = {}

        historical_career = history.get(
            "career_through_last_season",
            {},
        )

        if not isinstance(
            historical_career,
            dict,
        ):
            historical_career = {}

        last_season = history.get(
            "last_season",
            {},
        )

        if not isinstance(
            last_season,
            dict,
        ):
            last_season = {}

        historical_career_block = (
            build_stat_block_from_totals(
                games=safe_int(
                    historical_career.get(
                        "games"
                    )
                ),
                totals=normalize_totals(
                    historical_career.get(
                        "totals"
                    )
                ),
            )
        )

        last_season_block = (
            build_stat_block_from_totals(
                games=safe_int(
                    last_season.get(
                        "games"
                    )
                ),
                totals=normalize_totals(
                    last_season.get(
                        "totals"
                    )
                ),
            )
        )

        current_block = (
            current_stats.get(
                player_id,
                empty_stat_block(),
            )
        )

        career_block = (
            combine_stat_blocks(
                historical_career_block,
                current_block,
            )
        )

        historical_seasons = (
            historical_career.get(
                "seasons",
                [],
            )
        )

        if not isinstance(
            historical_seasons,
            list,
        ):
            historical_seasons = []

        career_seasons = [
            clean_text(season)
            for season
            in historical_seasons
            if clean_text(season)
        ]

        if (
            current_block["games"] > 0
            and CURRENT_SEASON
            not in career_seasons
        ):
            career_seasons.append(
                CURRENT_SEASON
            )

        career_seasons = sorted(
            set(career_seasons)
        )

        output.append(
            {
                **player,
                "current_season": {
                    "season": (
                        CURRENT_SEASON
                    ),
                    **current_block,
                },
                "last_season": {
                    "season": (
                        LAST_SEASON
                    ),
                    **last_season_block,
                },
                "career": {
                    "seasons": (
                        career_seasons
                    ),
                    "season_count": len(
                        career_seasons
                    ),
                    **career_block,
                },
            }
        )

    output.sort(
        key=lambda item: (
            item["player_name"].lower(),
            item["player_id"],
        )
    )

    return output


# ============================================================
# EXISTING OUTPUT FALLBACK
# ============================================================

def use_existing_output_fallback(
    reason: Exception,
) -> None:
    print()
    print("=" * 70)
    print("NBA PLAYER STATS FALLBACK")
    print("=" * 70)
    print()
    print(
        "Current NBA player game logs "
        "are unavailable."
    )
    print(
        f"Reason: "
        f"{type(reason).__name__}: {reason}"
    )
    print()

    if not OUTPUT_FILE.exists():
        raise FileNotFoundError(
            "NBA player stats fallback "
            f"not found: {OUTPUT_FILE}"
        ) from reason

    payload = load_json(
        OUTPUT_FILE
    )

    players = payload.get(
        "players"
    )

    if (
        not isinstance(players, list)
        or not players
    ):
        raise ValueError(
            "Existing NBA player stats "
            "fallback is invalid."
        ) from reason

    write_json(
        WEB_OUTPUT_FILE,
        payload,
    )

    print(
        f"Preserved existing stats for "
        f"{len(players):,} players."
    )
    print(
        f"Model: {OUTPUT_FILE}"
    )
    print(
        f"Web:   {WEB_OUTPUT_FILE}"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print()
    print("=" * 70)
    print("BUILDING NBA PLAYER STATISTICS")
    print("=" * 70)

    # --------------------------------------------------------
    # Current roster reference
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("LOADING NBA PLAYER REFERENCE")
    print("=" * 70)
    print()

    players_payload = load_json(
        PLAYERS_FILE
    )

    players_by_id = (
        build_player_reference(
            players_payload
        )
    )

    current_player_ids = set(
        players_by_id.keys()
    )

    print(
        f"Current roster players: "
        f"{len(players_by_id):,}"
    )

    # --------------------------------------------------------
    # Historical baseline
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("LOADING HISTORICAL BASELINE")
    print("=" * 70)
    print()

    history_payload = (
        load_or_create_history(
            players_by_id
        )
    )

    history_players = (
        history_payload.get(
            "players",
            {},
        )
    )

    print(
        f"Historical baseline through: "
        f"{LAST_SEASON}"
    )
    print(
        f"Historical player records:   "
        f"{len(history_players):,}"
    )

    # --------------------------------------------------------
    # Current season only
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("FETCHING CURRENT NBA SEASON")
    print("=" * 70)
    print()

    try:
        frame = (
            fetch_current_season_game_logs()
        )

    except Exception as exc:
        use_existing_output_fallback(
            exc
        )
        return

    current_stats = (
        aggregate_current_season(
            frame=frame,
            current_player_ids=(
                current_player_ids
            ),
        )
    )

    # --------------------------------------------------------
    # Build final output
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BUILDING PLAYER STAT VIEWS")
    print("=" * 70)
    print()

    player_stats = build_player_stats(
        players_by_id=players_by_id,
        history_payload=history_payload,
        current_stats=current_stats,
    )

    players_with_current = sum(
        1
        for player in player_stats
        if player[
            "current_season"
        ]["games"] > 0
    )

    players_with_last = sum(
        1
        for player in player_stats
        if player[
            "last_season"
        ]["games"] > 0
    )

    players_with_career = sum(
        1
        for player in player_stats
        if player[
            "career"
        ]["games"] > 0
    )

    payload = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "league": "NBA",
        "season_type": SEASON_TYPE,
        "current_season": (
            CURRENT_SEASON
        ),
        "last_season": LAST_SEASON,
        "historical_baseline_through": (
            LAST_SEASON
        ),
        "views": {
            "periods": [
                {
                    "key": (
                        "current_season"
                    ),
                    "label": (
                        "Current Season"
                    ),
                    "season": (
                        CURRENT_SEASON
                    ),
                },
                {
                    "key": (
                        "last_season"
                    ),
                    "label": (
                        "Last Season"
                    ),
                    "season": (
                        LAST_SEASON
                    ),
                },
                {
                    "key": "career",
                    "label": "Career",
                },
            ],
            "stat_types": [
                {
                    "key": "per_game",
                    "label": "Per Game",
                },
                {
                    "key": "totals",
                    "label": "Totals",
                },
            ],
        },
        "player_count": len(
            player_stats
        ),
        "metadata": {
            "source": "NBA Stats",
            "historical_source": (
                "stored baseline"
            ),
            "daily_live_season": (
                CURRENT_SEASON
            ),
            "current_api_rows": len(
                frame
            ),
            "current_roster_players": (
                len(players_by_id)
            ),
            "players_with_current_season_games": (
                players_with_current
            ),
            "players_with_last_season_games": (
                players_with_last
            ),
            "players_with_career_games": (
                players_with_career
            ),
        },
        "players": player_stats,
    }

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if not player_stats:
        raise RuntimeError(
            "NBA player stats build "
            "returned zero players."
        )

    if players_with_career <= 0:
        raise RuntimeError(
            "NBA player stats build "
            "returned zero career history."
        )

    # --------------------------------------------------------
    # Save
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("SAVING NBA PLAYER STATISTICS")
    print("=" * 70)
    print()

    write_json(
        OUTPUT_FILE,
        payload,
    )

    write_json(
        WEB_OUTPUT_FILE,
        payload,
    )

    print(
        f"Model: {OUTPUT_FILE}"
    )
    print(
        f"Web:   {WEB_OUTPUT_FILE}"
    )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("NBA PLAYER STATISTICS SUMMARY")
    print("=" * 70)
    print()

    print(
        f"Current roster players:      "
        f"{len(player_stats):,}"
    )
    print(
        f"Players with career games:   "
        f"{players_with_career:,}"
    )
    print(
        f"Players with last season:    "
        f"{players_with_last:,}"
    )
    print(
        f"Players with current season: "
        f"{players_with_current:,}"
    )
    print(
        f"Current-season API rows:     "
        f"{len(frame):,}"
    )

    print()
    print("=" * 70)
    print(
        "NBA PLAYER STATISTICS BUILD COMPLETE"
    )
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()