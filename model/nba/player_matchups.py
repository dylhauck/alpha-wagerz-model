from __future__ import annotations

import json
import math
import time
from collections import defaultdict
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
NBA_NEXT_DIR = NBA_DIR / "next"

WEB_NBA_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nba"
)
WEB_NBA_NEXT_DIR = WEB_NBA_DIR / "next"

PLAYERS_FILE = NBA_DIR / "players.json"
CURRENT_SLATE_FILE = NBA_DIR / "slate.json"
NEXT_SLATE_FILE = NBA_NEXT_DIR / "slate.json"

OUTPUT_FILE = NBA_DIR / "player_matchups.json"
NEXT_OUTPUT_FILE = NBA_NEXT_DIR / "player_matchups.json"

WEB_OUTPUT_FILE = WEB_NBA_DIR / "player_matchups.json"
WEB_NEXT_OUTPUT_FILE = WEB_NBA_NEXT_DIR / "player_matchups.json"


# ============================================================
# SEASONS
# ============================================================

CURRENT_SEASON = "2026-27"
LAST_SEASON = "2025-26"

LAST_3_SEASONS = [
    "2023-24",
    "2024-25",
    "2025-26",
]

ALL_SEASONS = [
    "2023-24",
    "2024-25",
    "2025-26",
    "2026-27",
]

SEASON_TYPE = "Regular Season"

REQUEST_TIMEOUT = 30
REQUEST_DELAY_SECONDS = 1.0
MAX_RETRIES = 3


# ============================================================
# TEAM ABBREVIATION NORMALIZATION
# ============================================================

TEAM_ABBREVIATION_MAP = {
    "ATL": "ATL",
    "BKN": "BKN",
    "BOS": "BOS",
    "CHA": "CHA",
    "CHI": "CHI",
    "CLE": "CLE",
    "DAL": "DAL",
    "DEN": "DEN",
    "DET": "DET",
    "GSW": "GSW",
    "HOU": "HOU",
    "IND": "IND",
    "LAC": "LAC",
    "LAL": "LAL",
    "MEM": "MEM",
    "MIA": "MIA",
    "MIL": "MIL",
    "MIN": "MIN",
    "NOP": "NOP",
    "NO": "NOP",
    "NYK": "NYK",
    "OKC": "OKC",
    "ORL": "ORL",
    "PHI": "PHI",
    "PHX": "PHX",
    "POR": "POR",
    "SAC": "SAC",
    "SAS": "SAS",
    "SA": "SAS",
    "TOR": "TOR",
    "UTA": "UTA",
    "WAS": "WAS",
}


# ============================================================
# HELPERS
# ============================================================

def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")

    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            payload,
            f,
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


def round_stat(value: float, digits: int = 1) -> float:
    return round(float(value), digits)


def pct(made: float, attempted: float) -> float:
    if attempted <= 0:
        return 0.0

    return round(made / attempted, 3)


def normalize_team_abbreviation(value: Any) -> str:
    abbr = clean_text(value).upper()

    return TEAM_ABBREVIATION_MAP.get(abbr, abbr)


def extract_opponent(matchup: Any) -> str:
    """
    NBA MATCHUP examples:

        LAL vs. BOS
        LAL @ BOS

    The opponent is always the final team abbreviation.
    """

    text = clean_text(matchup).upper()

    if not text:
        return ""

    if " VS. " in text:
        opponent = text.split(" VS. ", 1)[1]
        return normalize_team_abbreviation(opponent)

    if " VS " in text:
        opponent = text.split(" VS ", 1)[1]
        return normalize_team_abbreviation(opponent)

    if " @ " in text:
        opponent = text.split(" @ ", 1)[1]
        return normalize_team_abbreviation(opponent)

    parts = text.split()

    if parts:
        return normalize_team_abbreviation(parts[-1])

    return ""


def extract_game_date(value: Any) -> str:
    text = clean_text(value)

    if not text:
        return ""

    parsed = pd.to_datetime(text, errors="coerce")

    if pd.isna(parsed):
        return text

    return parsed.strftime("%Y-%m-%d")


# ============================================================
# PLAYERS
# ============================================================

def build_player_reference(
    payload: dict[str, Any],
) -> tuple[
    dict[int, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    players = payload.get("players", [])

    if not isinstance(players, list) or not players:
        raise ValueError(
            f"No players found in {PLAYERS_FILE}"
        )

    by_id: dict[int, dict[str, Any]] = {}
    by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for player in players:
        if not isinstance(player, dict):
            continue

        player_id = safe_int(player.get("player_id"))

        if player_id <= 0:
            continue

        team = normalize_team_abbreviation(
            player.get("team")
        )

        record = {
            "player_id": player_id,
            "player_name": clean_text(
                player.get("player_name")
            ),
            "team": team,
            "team_id": safe_int(
                player.get("team_id")
            ),
            "position": (
                clean_text(player.get("position"))
                or "N/A"
            ),
            "position_group": (
                clean_text(
                    player.get("position_group")
                )
                or "N/A"
            ),
            "number": clean_text(
                player.get("number")
            ),
        }

        by_id[player_id] = record

        if team:
            by_team[team].append(record)

    for team in by_team:
        by_team[team].sort(
            key=lambda item: (
                item["position"],
                item["player_name"],
            )
        )

    return by_id, dict(by_team)


# ============================================================
# NBA API
# ============================================================

def fetch_season_game_logs(
    season: str,
) -> pd.DataFrame:
    """
    Fetch every NBA player game log for one regular season.

    This is intentionally one bulk request per season rather
    than hundreds of player-specific requests.
    """

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(
                f"  Fetching {season} player game logs "
                f"(attempt {attempt}/{MAX_RETRIES})..."
            )

            response = playergamelogs.PlayerGameLogs(
                season_nullable=season,
                season_type_nullable=SEASON_TYPE,
                league_id_nullable="00",
                timeout=REQUEST_TIMEOUT,
            )

            frames = response.get_data_frames()

            if not frames:
                print(
                    f"    {season}: no data frame returned"
                )
                return pd.DataFrame()

            frame = frames[0].copy()

            print(
                f"    {season}: "
                f"{len(frame):,} player-game rows"
            )

            return frame

        except Exception as exc:
            last_error = exc

            print(
                f"    ERROR: {type(exc).__name__}: {exc}"
            )

            if attempt < MAX_RETRIES:
                wait_seconds = attempt * 3

                print(
                    f"    Retrying in "
                    f"{wait_seconds} seconds..."
                )

                time.sleep(wait_seconds)

    if season == CURRENT_SEASON:
        print()
        print(
            f"  WARNING: Current season {season} "
            f"could not be loaded."
        )
        print(
            "  This is allowed before current-season "
            "regular-season games exist."
        )
        print()

        return pd.DataFrame()

    raise RuntimeError(
        f"Unable to fetch NBA player game logs "
        f"for {season}"
    ) from last_error


# ============================================================
# NORMALIZE GAME LOGS
# ============================================================

def normalize_game_logs(
    frame: pd.DataFrame,
    season: str,
) -> list[dict[str, Any]]:
    if frame.empty:
        return []

    records: list[dict[str, Any]] = []

    for _, row in frame.iterrows():
        player_id = safe_int(row.get("PLAYER_ID"))

        if player_id <= 0:
            continue

        matchup = clean_text(row.get("MATCHUP"))
        opponent = extract_opponent(matchup)

        if not opponent:
            continue

        records.append(
            {
                "season": season,
                "player_id": player_id,
                "player_name": clean_text(
                    row.get("PLAYER_NAME")
                ),
                "team": normalize_team_abbreviation(
                    row.get("TEAM_ABBREVIATION")
                ),
                "opponent": opponent,
                "game_id": clean_text(
                    row.get("GAME_ID")
                ),
                "game_date": extract_game_date(
                    row.get("GAME_DATE")
                ),
                "matchup": matchup,
                "min": safe_float(row.get("MIN")),
                "pts": safe_float(row.get("PTS")),
                "reb": safe_float(row.get("REB")),
                "ast": safe_float(row.get("AST")),
                "stl": safe_float(row.get("STL")),
                "blk": safe_float(row.get("BLK")),
                "tov": safe_float(row.get("TOV")),
                "fgm": safe_float(row.get("FGM")),
                "fga": safe_float(row.get("FGA")),
                "fg3m": safe_float(row.get("FG3M")),
                "fg3a": safe_float(row.get("FG3A")),
                "ftm": safe_float(row.get("FTM")),
                "fta": safe_float(row.get("FTA")),
                "fantasy_points": safe_float(
                    row.get("NBA_FANTASY_PTS")
                ),
            }
        )

    return records


# ============================================================
# AGGREGATION
# ============================================================

def empty_stats() -> dict[str, Any]:
    return {
        "games": 0,
        "min_per_game": 0.0,
        "pts_per_game": 0.0,
        "fg3m_per_game": 0.0,
        "reb_per_game": 0.0,
        "ast_per_game": 0.0,
        "stl_per_game": 0.0,
        "blk_per_game": 0.0,
        "tov_per_game": 0.0,
        "fg_pct": 0.0,
        "fg3_pct": 0.0,
        "ft_pct": 0.0,
        "fantasy_per_game": 0.0,
    }


def aggregate_rows(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not rows:
        return empty_stats()

    games = len(rows)

    total_min = sum(row["min"] for row in rows)
    total_pts = sum(row["pts"] for row in rows)
    total_reb = sum(row["reb"] for row in rows)
    total_ast = sum(row["ast"] for row in rows)
    total_stl = sum(row["stl"] for row in rows)
    total_blk = sum(row["blk"] for row in rows)
    total_tov = sum(row["tov"] for row in rows)

    total_fgm = sum(row["fgm"] for row in rows)
    total_fga = sum(row["fga"] for row in rows)

    total_fg3m = sum(row["fg3m"] for row in rows)
    total_fg3a = sum(row["fg3a"] for row in rows)

    total_ftm = sum(row["ftm"] for row in rows)
    total_fta = sum(row["fta"] for row in rows)

    total_fantasy = sum(
        row["fantasy_points"]
        for row in rows
    )

    return {
        "games": games,
        "min_per_game": round_stat(
            total_min / games
        ),
        "pts_per_game": round_stat(
            total_pts / games
        ),
        "reb_per_game": round_stat(
            total_reb / games
        ),
        "ast_per_game": round_stat(
            total_ast / games
        ),
        "stl_per_game": round_stat(
            total_stl / games
        ),
        "blk_per_game": round_stat(
            total_blk / games
        ),
        "tov_per_game": round_stat(
            total_tov / games
        ),
        "fg3m_per_game": round_stat(
            total_fg3m / games
        ),
        "fg_pct": pct(
            total_fgm,
            total_fga,
        ),
        "fg3_pct": pct(
            total_fg3m,
            total_fg3a,
        ),
        "ft_pct": pct(
            total_ftm,
            total_fta,
        ),
        "fantasy_per_game": round_stat(
            total_fantasy / games
        ),
    }


def build_matchup_database(
    all_logs: list[dict[str, Any]],
    players_by_id: dict[int, dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    """
    Organize all historical game logs by:

        player_id
            -> opponent
                -> season
                    -> rows
    """

    grouped: dict[
        int,
        dict[
            str,
            dict[
                str,
                list[dict[str, Any]]
            ]
        ]
    ] = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(list)
        )
    )

    for row in all_logs:
        player_id = row["player_id"]

        # Only retain players on the CURRENT roster reference.
        # This prevents hundreds of former NBA players from
        # bloating the frontend matchup file.
        if player_id not in players_by_id:
            continue

        opponent = row["opponent"]
        season = row["season"]

        grouped[player_id][opponent][season].append(
            row
        )

    database: dict[int, dict[str, Any]] = {}

    for player_id, opponents in grouped.items():
        player = players_by_id[player_id]

        opponent_payload: dict[str, Any] = {}

        for opponent, seasons in opponents.items():
            season_payload: dict[str, Any] = {}

            for season in ALL_SEASONS:
                season_rows = seasons.get(
                    season,
                    [],
                )

                season_payload[season] = {
                    **aggregate_rows(season_rows),
                    "game_dates": [
                        row["game_date"]
                        for row in season_rows
                        if row["game_date"]
                    ],
                }

            current_rows = seasons.get(
                CURRENT_SEASON,
                [],
            )

            last_season_rows = seasons.get(
                LAST_SEASON,
                [],
            )

            last_3_rows: list[dict[str, Any]] = []

            for season in LAST_3_SEASONS:
                last_3_rows.extend(
                    seasons.get(season, [])
                )

            opponent_payload[opponent] = {
                "current_season": {
                    "season": CURRENT_SEASON,
                    **aggregate_rows(
                        current_rows
                    ),
                },
                "last_season": {
                    "season": LAST_SEASON,
                    **aggregate_rows(
                        last_season_rows
                    ),
                },
                "last_3_seasons": {
                    "seasons": LAST_3_SEASONS,
                    **aggregate_rows(
                        last_3_rows
                    ),
                },
                "by_season": season_payload,
            }

        database[player_id] = {
            **player,
            "opponents": opponent_payload,
        }

    return database


# ============================================================
# SLATE HELPERS
# ============================================================

def get_games_from_slate(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Supports the NBA slate payload produced by our existing
    providers/nba/nba_data.py while being tolerant of a couple of
    common wrapper names.
    """

    candidates = [
        payload.get("games"),
        payload.get("slate"),
        payload.get("matchups"),
    ]

    for candidate in candidates:
        if isinstance(candidate, list):
            return [
                game
                for game in candidate
                if isinstance(game, dict)
            ]

    return []


def get_team_from_game(
    game: dict[str, Any],
    side: str,
) -> str:
    keys = [
        f"{side}_team",
        f"{side}_team_abbr",
        f"{side}_abbr",
        side,
    ]

    for key in keys:
        value = game.get(key)

        if isinstance(value, dict):
            for nested_key in (
                "abbr",
                "abbreviation",
                "team",
            ):
                nested_value = value.get(nested_key)

                if nested_value:
                    return normalize_team_abbreviation(
                        nested_value
                    )

        elif value:
            return normalize_team_abbreviation(value)

    return ""


def get_game_id(
    game: dict[str, Any],
) -> str:
    for key in (
        "game_id",
        "gameId",
        "id",
    ):
        value = game.get(key)

        if value is not None:
            return clean_text(value)

    return ""


def get_game_date(
    game: dict[str, Any],
) -> str:
    for key in (
        "game_date",
        "date",
        "gameDate",
        "game_date_est",
    ):
        value = game.get(key)

        if value:
            return extract_game_date(value)

    return ""


# ============================================================
# BUILD SLATE MATCHUPS
# ============================================================

def build_team_players_vs_opponent(
    team: str,
    opponent: str,
    players_by_team: dict[
        str,
        list[dict[str, Any]]
    ],
    matchup_database: dict[
        int,
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for player in players_by_team.get(team, []):
        player_id = player["player_id"]

        historical = matchup_database.get(
            player_id,
            {},
        )

        opponent_data = (
            historical
            .get("opponents", {})
            .get(opponent)
        )

        if opponent_data is None:
            opponent_data = {
                "current_season": {
                    "season": CURRENT_SEASON,
                    **empty_stats(),
                },
                "last_season": {
                    "season": LAST_SEASON,
                    **empty_stats(),
                },
                "last_3_seasons": {
                    "seasons": LAST_3_SEASONS,
                    **empty_stats(),
                },
                "by_season": {
                    season: {
                        **empty_stats(),
                        "game_dates": [],
                    }
                    for season in ALL_SEASONS
                },
            }

        output.append(
            {
                "player_id": player_id,
                "player_name": player[
                    "player_name"
                ],
                "team": team,
                "opponent": opponent,
                "position": player[
                    "position"
                ],
                "position_group": player[
                    "position_group"
                ],
                "number": player["number"],
                "splits": opponent_data,
            }
        )

    return output


def build_slate_payload(
    slate_payload: dict[str, Any],
    slate_type: str,
    players_by_team: dict[
        str,
        list[dict[str, Any]]
    ],
    matchup_database: dict[
        int,
        dict[str, Any]
    ],
) -> dict[str, Any]:
    games = get_games_from_slate(slate_payload)

    matchup_games: list[dict[str, Any]] = []

    for game in games:
        away_team = get_team_from_game(
            game,
            "away",
        )
        home_team = get_team_from_game(
            game,
            "home",
        )

        if not away_team or not home_team:
            print(
                "  WARNING: skipping slate game "
                "because team abbreviations "
                "could not be identified:"
            )
            print(f"    {game}")
            continue

        away_players = (
            build_team_players_vs_opponent(
                team=away_team,
                opponent=home_team,
                players_by_team=players_by_team,
                matchup_database=matchup_database,
            )
        )

        home_players = (
            build_team_players_vs_opponent(
                team=home_team,
                opponent=away_team,
                players_by_team=players_by_team,
                matchup_database=matchup_database,
            )
        )

        matchup_games.append(
            {
                "game_id": get_game_id(game),
                "game_date": get_game_date(game),
                "away_team": away_team,
                "home_team": home_team,
                "away_players": away_players,
                "home_players": home_players,
            }
        )

    slate_date = clean_text(
        slate_payload.get("slate_date")
    )

    if not slate_date and matchup_games:
        slate_date = matchup_games[0][
            "game_date"
        ]

    return {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "league": "NBA",
        "slate_type": slate_type,
        "slate_date": slate_date,
        "current_season": CURRENT_SEASON,
        "last_season": LAST_SEASON,
        "last_3_seasons": LAST_3_SEASONS,
        "filters": [
            {
                "key": "current_season",
                "label": "Current Season",
                "seasons": [
                    CURRENT_SEASON
                ],
            },
            {
                "key": "last_season",
                "label": "Last Season",
                "seasons": [
                    LAST_SEASON
                ],
            },
            {
                "key": "last_3_seasons",
                "label": "Last 3 Seasons",
                "seasons": (
                    LAST_3_SEASONS
                ),
            },
        ],
        "game_count": len(matchup_games),
        "games": matchup_games,
    }


# ============================================================
# MAIN
# ============================================================
def use_existing_matchup_fallback(
    reason: Exception,
) -> None:
    print()
    print(
        "NBA Stats player game logs are unavailable."
    )
    print(
        f"Reason: {type(reason).__name__}: {reason}"
    )
    print(
        "Preserving existing NBA player matchup data."
    )

    required_files = [
        OUTPUT_FILE,
        NEXT_OUTPUT_FILE,
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(
                f"NBA player matchup fallback not found: {path}"
            ) from reason

        payload = load_json(path)

        games = payload.get("games")

        if not isinstance(games, list):
            raise ValueError(
                f"NBA player matchup fallback is invalid: {path}"
            ) from reason

    current_payload = load_json(
        OUTPUT_FILE
    )

    next_payload = load_json(
        NEXT_OUTPUT_FILE
    )

    write_json(
        WEB_OUTPUT_FILE,
        current_payload,
    )

    write_json(
        WEB_NEXT_OUTPUT_FILE,
        next_payload,
    )

    print(
        f"Fallback current: {OUTPUT_FILE}"
    )
    print(
        f"Fallback future:  {NEXT_OUTPUT_FILE}"
    )
    print(
        "NBA PLAYER MATCHUP HISTORY COMPLETE "
        "(existing fallback)"
    )

def main() -> None:
    print()
    print("=" * 70)
    print("BUILDING NBA PLAYER MATCHUP HISTORY")
    print("=" * 70)

    print()
    print("Seasons:")
    for season in ALL_SEASONS:
        print(f"  - {season}")

    print()
    print("=" * 70)
    print("LOADING NBA PLAYER REFERENCE")
    print("=" * 70)

    players_payload = load_json(
        PLAYERS_FILE
    )

    players_by_id, players_by_team = (
        build_player_reference(
            players_payload
        )
    )

    print(
        f"Current players: "
        f"{len(players_by_id):,}"
    )
    print(
        f"Current teams:   "
        f"{len(players_by_team):,}"
    )

    print()
    print("=" * 70)
    print("FETCHING NBA PLAYER GAME LOGS")
    print("=" * 70)

    all_logs: list[dict[str, Any]] = []

    season_counts: dict[str, int] = {}

    for index, season in enumerate(
        ALL_SEASONS,
        start=1,
    ):
        print()
        print(
            f"[{index}/{len(ALL_SEASONS)}] "
            f"{season}"
        )

        try:
            frame = fetch_season_game_logs(
                season
            )

        except Exception as exc:
            use_existing_matchup_fallback(
                exc
            )
            return

        normalized = normalize_game_logs(
            frame,
            season,
        )

        season_counts[season] = len(
            normalized
        )

        all_logs.extend(normalized)

        print(
            f"    Normalized: "
            f"{len(normalized):,} rows"
        )

        if index < len(ALL_SEASONS):
            time.sleep(
                REQUEST_DELAY_SECONDS
            )

    print()
    print("=" * 70)
    print("BUILDING MATCHUP DATABASE")
    print("=" * 70)

    matchup_database = (
        build_matchup_database(
            all_logs=all_logs,
            players_by_id=players_by_id,
        )
    )

    players_with_history = len(
        matchup_database
    )

    opponent_pairs = sum(
        len(
            player_data.get(
                "opponents",
                {},
            )
        )
        for player_data
        in matchup_database.values()
    )

    print(
        f"Players with historical data: "
        f"{players_with_history:,}"
    )
    print(
        f"Player/opponent combinations: "
        f"{opponent_pairs:,}"
    )

    print()
    print("=" * 70)
    print("LOADING NBA SLATES")
    print("=" * 70)

    current_slate = load_json(
        CURRENT_SLATE_FILE
    )

    next_slate = load_json(
        NEXT_SLATE_FILE
    )

    current_games = get_games_from_slate(
        current_slate
    )

    next_games = get_games_from_slate(
        next_slate
    )

    print(
        f"Current slate games: "
        f"{len(current_games)}"
    )
    print(
        f"Future slate games:  "
        f"{len(next_games)}"
    )

    print()
    print("=" * 70)
    print("BUILDING CURRENT SLATE MATCHUPS")
    print("=" * 70)

    current_payload = build_slate_payload(
        slate_payload=current_slate,
        slate_type="current",
        players_by_team=players_by_team,
        matchup_database=matchup_database,
    )

    print(
        f"Built "
        f"{current_payload['game_count']} "
        f"current slate games"
    )

    print()
    print("=" * 70)
    print("BUILDING FUTURE SLATE MATCHUPS")
    print("=" * 70)

    next_payload = build_slate_payload(
        slate_payload=next_slate,
        slate_type="next",
        players_by_team=players_by_team,
        matchup_database=matchup_database,
    )

    print(
        f"Built "
        f"{next_payload['game_count']} "
        f"future slate games"
    )

    # Add source metadata.
    metadata = {
        "source": "NBA Stats",
        "season_type": SEASON_TYPE,
        "season_row_counts": season_counts,
        "total_player_game_rows": len(
            all_logs
        ),
        "current_player_count": len(
            players_by_id
        ),
        "players_with_history": (
            players_with_history
        ),
        "player_opponent_combinations": (
            opponent_pairs
        ),
    }

    current_payload["metadata"] = metadata
    next_payload["metadata"] = metadata

    print()
    print("=" * 70)
    print("SAVING NBA PLAYER MATCHUP DATA")
    print("=" * 70)

    write_json(
        OUTPUT_FILE,
        current_payload,
    )

    write_json(
        NEXT_OUTPUT_FILE,
        next_payload,
    )

    write_json(
        WEB_OUTPUT_FILE,
        current_payload,
    )

    write_json(
        WEB_NEXT_OUTPUT_FILE,
        next_payload,
    )

    print()
    print(f"Model current: {OUTPUT_FILE}")
    print(f"Model future:  {NEXT_OUTPUT_FILE}")
    print(f"Web current:   {WEB_OUTPUT_FILE}")
    print(f"Web future:    {WEB_NEXT_OUTPUT_FILE}")

    print()
    print("=" * 70)
    print("NBA PLAYER MATCHUP HISTORY SUMMARY")
    print("=" * 70)

    print()
    print("Player-game rows by season:")

    for season in ALL_SEASONS:
        print(
            f"  {season}: "
            f"{season_counts.get(season, 0):,}"
        )

    print()
    print(
        f"Current roster players: "
        f"{len(players_by_id):,}"
    )
    print(
        f"Players with history:   "
        f"{players_with_history:,}"
    )
    print(
        f"Opponent combinations:  "
        f"{opponent_pairs:,}"
    )
    print(
        f"Current slate games:     "
        f"{current_payload['game_count']}"
    )
    print(
        f"Future slate games:      "
        f"{next_payload['game_count']}"
    )

    print()
    print("=" * 70)
    print(
        "NBA PLAYER MATCHUP HISTORY BUILD COMPLETE"
    )
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()

