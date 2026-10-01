from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from nba_api.stats.endpoints import leaguegamelog


# ============================================================
# CONFIG
# ============================================================

CURRENT_SEASON = "2026-27"
LAST_SEASON = "2025-26"

SEASON_TYPE = "Regular Season"

REQUEST_TIMEOUT = 30
MAX_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5

ROOT_DIR = Path(__file__).resolve().parents[2]
NBA_DIR = ROOT_DIR / "data" / "processed" / "nba"

OUTPUT_FILE = NBA_DIR / "team_stats.json"
MARKET_HISTORY_FILE = NBA_DIR / "market_history.json"

WEB_ROOT = ROOT_DIR.parent / "alpha-wagerz-web"
WEB_NBA_DIR = WEB_ROOT / "public" / "data" / "nba"
WEB_OUTPUT_FILE = WEB_NBA_DIR / "team_stats.json"


# ============================================================
# NBA TEAM REFERENCE
# ============================================================

TEAM_INFO = {
    "ATL": {
        "name": "Atlanta Hawks",
        "conference": "East",
    },
    "BOS": {
        "name": "Boston Celtics",
        "conference": "East",
    },
    "BKN": {
        "name": "Brooklyn Nets",
        "conference": "East",
    },
    "CHA": {
        "name": "Charlotte Hornets",
        "conference": "East",
    },
    "CHI": {
        "name": "Chicago Bulls",
        "conference": "East",
    },
    "CLE": {
        "name": "Cleveland Cavaliers",
        "conference": "East",
    },
    "DAL": {
        "name": "Dallas Mavericks",
        "conference": "West",
    },
    "DEN": {
        "name": "Denver Nuggets",
        "conference": "West",
    },
    "DET": {
        "name": "Detroit Pistons",
        "conference": "East",
    },
    "GSW": {
        "name": "Golden State Warriors",
        "conference": "West",
    },
    "HOU": {
        "name": "Houston Rockets",
        "conference": "West",
    },
    "IND": {
        "name": "Indiana Pacers",
        "conference": "East",
    },
    "LAC": {
        "name": "LA Clippers",
        "conference": "West",
    },
    "LAL": {
        "name": "Los Angeles Lakers",
        "conference": "West",
    },
    "MEM": {
        "name": "Memphis Grizzlies",
        "conference": "West",
    },
    "MIA": {
        "name": "Miami Heat",
        "conference": "East",
    },
    "MIL": {
        "name": "Milwaukee Bucks",
        "conference": "East",
    },
    "MIN": {
        "name": "Minnesota Timberwolves",
        "conference": "West",
    },
    "NOP": {
        "name": "New Orleans Pelicans",
        "conference": "West",
    },
    "NYK": {
        "name": "New York Knicks",
        "conference": "East",
    },
    "OKC": {
        "name": "Oklahoma City Thunder",
        "conference": "West",
    },
    "ORL": {
        "name": "Orlando Magic",
        "conference": "East",
    },
    "PHI": {
        "name": "Philadelphia 76ers",
        "conference": "East",
    },
    "PHX": {
        "name": "Phoenix Suns",
        "conference": "West",
    },
    "POR": {
        "name": "Portland Trail Blazers",
        "conference": "West",
    },
    "SAC": {
        "name": "Sacramento Kings",
        "conference": "West",
    },
    "SAS": {
        "name": "San Antonio Spurs",
        "conference": "West",
    },
    "TOR": {
        "name": "Toronto Raptors",
        "conference": "East",
    },
    "UTA": {
        "name": "Utah Jazz",
        "conference": "West",
    },
    "WAS": {
        "name": "Washington Wizards",
        "conference": "East",
    },
}


# ============================================================
# BASIC HELPERS
# ============================================================

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0

        return float(value)

    except (TypeError, ValueError):
        return 0.0


def safe_int(value: Any) -> int:
    try:
        if pd.isna(value):
            return 0

        return int(float(value))

    except (TypeError, ValueError):
        return 0


def round_stat(value: float) -> float:
    return round(float(value), 1)


def round_pct(value: float) -> float:
    return round(float(value), 3)


def ratio(
    numerator: float,
    denominator: float,
) -> float:
    if denominator <= 0:
        return 0.0

    return numerator / denominator


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
        )


def load_json(
    path: Path,
) -> dict[str, Any] | None:
    if not path.exists():
        return None

    try:
        with path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            payload = json.load(handle)

        if isinstance(payload, dict):
            return payload

    except Exception:
        pass

    return None


# ============================================================
# EMPTY STAT STRUCTURES
# ============================================================

def empty_totals() -> dict[str, float | int]:
    return {
        "min": 0.0,
        "pts": 0,
        "pts_allowed": 0,
        "point_diff": 0,
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
        "pts_allowed": 0.0,
        "point_diff": 0.0,
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


def empty_record() -> dict[str, float | int]:
    return {
        "wins": 0,
        "losses": 0,
        "win_pct": 0.0,
    }


def empty_season_block(
    season: str,
) -> dict[str, Any]:
    return {
        "season": season,
        "games": 0,
        "record": empty_record(),
        "per_game": empty_per_game(),
        "totals": empty_totals(),
        "percentages": empty_percentages(),
        "ats": None,
        "over_under": None,
    }


# ============================================================
# MARKET HISTORY
# ============================================================

def normalize_market_team(
    value: Any,
) -> str:
    team = str(
        value or ""
    ).strip().upper()

    aliases = {
        "NO": "NOP",
        "NY": "NYK",
        "SA": "SAS",
        "GS": "GSW",
        "UTAH": "UTA",
    }

    return aliases.get(
        team,
        team,
    )


def load_market_history() -> list[dict[str, Any]]:
    payload = load_json(
        MARKET_HISTORY_FILE,
    )

    if payload is None:
        print(
            "NBA market history unavailable; "
            "ATS / O-U will remain unavailable.",
            flush=True,
        )

        return []

    games = payload.get(
        "games",
    )

    if not isinstance(
        games,
        list,
    ):
        print(
            "NBA market history contains no valid games list; "
            "ATS / O-U will remain unavailable.",
            flush=True,
        )

        return []

    valid_games = [
        game
        for game in games
        if isinstance(
            game,
            dict,
        )
    ]

    print(
        f"NBA market history games loaded: "
        f"{len(valid_games):,}",
        flush=True,
    )

    return valid_games


def build_market_records(
    market_games: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Grade actual completed NBA games against historical
    closing spreads and totals.

    ATS:
        away_score + away_spread vs home_score
        home_score + home_spread vs away_score

    O/U:
        away_score + home_score vs closing total

    Pushes are included in the displayed record but excluded
    from the percentage denominator.
    """

    records: dict[
        str,
        dict[str, int],
    ] = defaultdict(
        lambda: {
            "ats_wins": 0,
            "ats_losses": 0,
            "ats_pushes": 0,
            "overs": 0,
            "unders": 0,
            "total_pushes": 0,
        }
    )

    for game in market_games:
        away_team = normalize_market_team(
            game.get("away_team"),
        )

        home_team = normalize_market_team(
            game.get("home_team"),
        )

        if (
            not away_team
            or not home_team
        ):
            continue

        if (
            away_team not in TEAM_INFO
            or home_team not in TEAM_INFO
        ):
            continue

        away_score_raw = game.get(
            "away_score",
        )

        home_score_raw = game.get(
            "home_score",
        )

        if (
            away_score_raw is None
            or home_score_raw is None
        ):
            continue

        try:
            away_score = float(
                away_score_raw
            )

            home_score = float(
                home_score_raw
            )

        except (
            TypeError,
            ValueError,
        ):
            continue

        # ----------------------------------------------------
        # ATS
        # ----------------------------------------------------

        away_spread_raw = game.get(
            "away_spread",
        )

        home_spread_raw = game.get(
            "home_spread",
        )

        if (
            away_spread_raw is not None
            and home_spread_raw is not None
        ):
            try:
                away_spread = float(
                    away_spread_raw
                )

                home_spread = float(
                    home_spread_raw
                )

            except (
                TypeError,
                ValueError,
            ):
                away_spread = None
                home_spread = None

            if (
                away_spread is not None
                and home_spread is not None
            ):
                away_ats_margin = (
                    away_score
                    + away_spread
                    - home_score
                )

                home_ats_margin = (
                    home_score
                    + home_spread
                    - away_score
                )

                if away_ats_margin > 0:
                    records[
                        away_team
                    ]["ats_wins"] += 1

                elif away_ats_margin < 0:
                    records[
                        away_team
                    ]["ats_losses"] += 1

                else:
                    records[
                        away_team
                    ]["ats_pushes"] += 1

                if home_ats_margin > 0:
                    records[
                        home_team
                    ]["ats_wins"] += 1

                elif home_ats_margin < 0:
                    records[
                        home_team
                    ]["ats_losses"] += 1

                else:
                    records[
                        home_team
                    ]["ats_pushes"] += 1

        # ----------------------------------------------------
        # OVER / UNDER
        # ----------------------------------------------------

        total_raw = game.get(
            "total",
        )

        if total_raw is not None:
            try:
                closing_total = float(
                    total_raw
                )

            except (
                TypeError,
                ValueError,
            ):
                closing_total = None

            if closing_total is not None:
                actual_total = (
                    away_score
                    + home_score
                )

                if actual_total > closing_total:
                    records[
                        away_team
                    ]["overs"] += 1

                    records[
                        home_team
                    ]["overs"] += 1

                elif actual_total < closing_total:
                    records[
                        away_team
                    ]["unders"] += 1

                    records[
                        home_team
                    ]["unders"] += 1

                else:
                    records[
                        away_team
                    ]["total_pushes"] += 1

                    records[
                        home_team
                    ]["total_pushes"] += 1

    result: dict[
        str,
        dict[str, Any],
    ] = {}

    for team, item in records.items():
        ats_wins = safe_int(
            item["ats_wins"],
        )

        ats_losses = safe_int(
            item["ats_losses"],
        )

        ats_pushes = safe_int(
            item["ats_pushes"],
        )

        ats_decisions = (
            ats_wins
            + ats_losses
        )

        ats_games = (
            ats_decisions
            + ats_pushes
        )

        overs = safe_int(
            item["overs"],
        )

        unders = safe_int(
            item["unders"],
        )

        total_pushes = safe_int(
            item["total_pushes"],
        )

        total_decisions = (
            overs
            + unders
        )

        total_games = (
            total_decisions
            + total_pushes
        )

        ats: dict[str, Any] | None

        if ats_games > 0:
            ats = {
                "wins": ats_wins,
                "losses": ats_losses,
                "pushes": ats_pushes,
                "record": (
                    f"{ats_wins}-"
                    f"{ats_losses}-"
                    f"{ats_pushes}"
                ),
                "games_with_line":
                    ats_games,
                "ats_pct": round_pct(
                    ratio(
                        ats_wins,
                        ats_decisions,
                    )
                ),
            }

        else:
            ats = None

        over_under: dict[str, Any] | None

        if total_games > 0:
            over_under = {
                "overs": overs,
                "unders": unders,
                "pushes": total_pushes,
                "record": (
                    f"{overs}-"
                    f"{unders}-"
                    f"{total_pushes}"
                ),
                "games_with_total":
                    total_games,
                "over_pct": round_pct(
                    ratio(
                        overs,
                        total_decisions,
                    )
                ),
                "under_pct": round_pct(
                    ratio(
                        unders,
                        total_decisions,
                    )
                ),
            }

        else:
            over_under = None

        result[team] = {
            "ats": ats,
            "over_under": over_under,
        }

    return result


# ============================================================
# FETCH TEAM GAME LOGS
# ============================================================

def fetch_team_game_logs(
    season: str,
) -> pd.DataFrame:
    last_error: Exception | None = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):
        try:
            print(
                f"Fetching {season} NBA team game logs "
                f"(attempt {attempt}/{MAX_ATTEMPTS})...",
                flush=True,
            )

            endpoint = leaguegamelog.LeagueGameLog(
                counter=0,
                direction="DESC",
                league_id="00",
                player_or_team_abbreviation="T",
                season=season,
                season_type_all_star=SEASON_TYPE,
                sorter="DATE",
                timeout=REQUEST_TIMEOUT,
            )

            frames = endpoint.get_data_frames()

            if not frames:
                print(
                    f"{season}: 0 team-game rows",
                    flush=True,
                )

                return pd.DataFrame()

            frame = frames[0].copy()

            print(
                f"{season}: {len(frame):,} team-game rows",
                flush=True,
            )

            return frame

        except Exception as exc:
            last_error = exc

            print(
                f"{season} team game log attempt "
                f"{attempt} failed: {exc}",
                flush=True,
            )

            if attempt < MAX_ATTEMPTS:
                time.sleep(
                    RETRY_DELAY_SECONDS,
                )

    if last_error is not None:
        raise last_error

    return pd.DataFrame()


# ============================================================
# OPPONENT POINTS
# ============================================================

def build_opponent_points(
    frame: pd.DataFrame,
) -> dict[tuple[str, int], float]:
    """
    LeagueGameLog returns one row per team per game.

    A completed NBA game normally has two rows sharing GAME_ID.

    The opposing row's PTS becomes PTS_ALLOWED.
    """

    opponent_points: dict[
        tuple[str, int],
        float,
    ] = {}

    if frame.empty:
        return opponent_points

    grouped = frame.groupby(
        "GAME_ID",
        dropna=False,
    )

    for game_id, game_rows in grouped:
        rows = list(
            game_rows.to_dict(
                orient="records",
            )
        )

        if len(rows) != 2:
            continue

        first = rows[0]
        second = rows[1]

        first_team_id = safe_int(
            first.get("TEAM_ID"),
        )

        second_team_id = safe_int(
            second.get("TEAM_ID"),
        )

        first_pts = safe_float(
            first.get("PTS"),
        )

        second_pts = safe_float(
            second.get("PTS"),
        )

        game_key = str(
            game_id
        )

        opponent_points[
            (
                game_key,
                first_team_id,
            )
        ] = second_pts

        opponent_points[
            (
                game_key,
                second_team_id,
            )
        ] = first_pts

    return opponent_points


# ============================================================
# AGGREGATION
# ============================================================

def aggregate_team_season(
    frame: pd.DataFrame,
    season: str,
) -> dict[str, dict[str, Any]]:
    if frame.empty:
        return {}

    opponent_points = (
        build_opponent_points(
            frame
        )
    )

    accumulators: dict[
        str,
        dict[str, Any],
    ] = defaultdict(
        lambda: {
            "team_id": 0,
            "team_name": "",
            "games": 0,
            "wins": 0,
            "losses": 0,
            "min": 0.0,
            "pts": 0.0,
            "pts_allowed": 0.0,
            "reb": 0.0,
            "ast": 0.0,
            "stl": 0.0,
            "blk": 0.0,
            "tov": 0.0,
            "fgm": 0.0,
            "fga": 0.0,
            "fg3m": 0.0,
            "fg3a": 0.0,
            "ftm": 0.0,
            "fta": 0.0,
        }
    )

    for row in frame.to_dict(
        orient="records",
    ):
        team = str(
            row.get(
                "TEAM_ABBREVIATION",
                "",
            )
            or ""
        ).strip().upper()

        if not team:
            continue

        team_id = safe_int(
            row.get("TEAM_ID"),
        )

        game_id = str(
            row.get(
                "GAME_ID",
                "",
            )
            or ""
        )

        team_pts = safe_float(
            row.get("PTS"),
        )

        allowed = opponent_points.get(
            (
                game_id,
                team_id,
            )
        )

        # Only count complete paired games so points allowed
        # and differential cannot silently become incorrect.
        if allowed is None:
            continue

        item = accumulators[
            team
        ]

        item["team_id"] = (
            team_id
        )

        team_name = str(
            row.get(
                "TEAM_NAME",
                "",
            )
            or ""
        ).strip()

        if team_name:
            item["team_name"] = (
                team_name
            )

        item["games"] += 1

        wl = str(
            row.get(
                "WL",
                "",
            )
            or ""
        ).strip().upper()

        if wl == "W":
            item["wins"] += 1

        elif wl == "L":
            item["losses"] += 1

        item["min"] += safe_float(
            row.get("MIN"),
        )

        item["pts"] += (
            team_pts
        )

        item["pts_allowed"] += (
            allowed
        )

        item["reb"] += safe_float(
            row.get("REB"),
        )

        item["ast"] += safe_float(
            row.get("AST"),
        )

        item["stl"] += safe_float(
            row.get("STL"),
        )

        item["blk"] += safe_float(
            row.get("BLK"),
        )

        item["tov"] += safe_float(
            row.get("TOV"),
        )

        item["fgm"] += safe_float(
            row.get("FGM"),
        )

        item["fga"] += safe_float(
            row.get("FGA"),
        )

        item["fg3m"] += safe_float(
            row.get("FG3M"),
        )

        item["fg3a"] += safe_float(
            row.get("FG3A"),
        )

        item["ftm"] += safe_float(
            row.get("FTM"),
        )

        item["fta"] += safe_float(
            row.get("FTA"),
        )

    result: dict[
        str,
        dict[str, Any],
    ] = {}

    for team, item in accumulators.items():
        games = safe_int(
            item["games"],
        )

        wins = safe_int(
            item["wins"],
        )

        losses = safe_int(
            item["losses"],
        )

        pts = safe_float(
            item["pts"],
        )

        pts_allowed = safe_float(
            item["pts_allowed"],
        )

        point_diff = (
            pts
            - pts_allowed
        )

        totals = {
            "min": round_stat(
                item["min"],
            ),
            "pts": round(
                pts
            ),
            "pts_allowed": round(
                pts_allowed
            ),
            "point_diff": round(
                point_diff
            ),
            "reb": round(
                item["reb"]
            ),
            "ast": round(
                item["ast"]
            ),
            "stl": round(
                item["stl"]
            ),
            "blk": round(
                item["blk"]
            ),
            "tov": round(
                item["tov"]
            ),
            "fgm": round(
                item["fgm"]
            ),
            "fga": round(
                item["fga"]
            ),
            "fg3m": round(
                item["fg3m"]
            ),
            "fg3a": round(
                item["fg3a"]
            ),
            "ftm": round(
                item["ftm"]
            ),
            "fta": round(
                item["fta"]
            ),
        }

        if games > 0:
            per_game = {
                "min": round_stat(
                    item["min"]
                    / games
                ),
                "pts": round_stat(
                    pts
                    / games
                ),
                "pts_allowed":
                    round_stat(
                        pts_allowed
                        / games
                    ),
                "point_diff":
                    round_stat(
                        point_diff
                        / games
                    ),
                "reb": round_stat(
                    item["reb"]
                    / games
                ),
                "ast": round_stat(
                    item["ast"]
                    / games
                ),
                "stl": round_stat(
                    item["stl"]
                    / games
                ),
                "blk": round_stat(
                    item["blk"]
                    / games
                ),
                "tov": round_stat(
                    item["tov"]
                    / games
                ),
                "fg3m": round_stat(
                    item["fg3m"]
                    / games
                ),
            }

        else:
            per_game = (
                empty_per_game()
            )

        percentages = {
            "fg_pct": round_pct(
                ratio(
                    item["fgm"],
                    item["fga"],
                )
            ),
            "fg3_pct": round_pct(
                ratio(
                    item["fg3m"],
                    item["fg3a"],
                )
            ),
            "ft_pct": round_pct(
                ratio(
                    item["ftm"],
                    item["fta"],
                )
            ),
        }

        record = {
            "wins": wins,
            "losses": losses,
            "win_pct": round_pct(
                ratio(
                    wins,
                    wins + losses,
                )
            ),
        }

        result[team] = {
            "season": season,
            "games": games,
            "record": record,
            "per_game": per_game,
            "totals": totals,
            "percentages": percentages,
            "ats": None,
            "over_under": None,
        }

    return result


# ============================================================
# BUILD TEAM PAYLOAD
# ============================================================

def build_team_payload(
    current_stats: dict[
        str,
        dict[str, Any],
    ],
    last_stats: dict[
        str,
        dict[str, Any],
    ],
    market_records: dict[
        str,
        dict[str, Any],
    ],
) -> dict[str, Any]:
    all_teams = set(
        TEAM_INFO.keys()
    )

    all_teams.update(
        current_stats.keys()
    )

    all_teams.update(
        last_stats.keys()
    )

    teams: list[
        dict[str, Any]
    ] = []

    for team in sorted(
        all_teams
    ):
        reference = (
            TEAM_INFO.get(
                team,
                {},
            )
        )

        current = (
            current_stats.get(
                team,
                empty_season_block(
                    CURRENT_SEASON,
                ),
            )
        )

        last = (
            last_stats.get(
                team,
                empty_season_block(
                    LAST_SEASON,
                ),
            )
        )

        market = (
            market_records.get(
                team
            )
        )

        # The current market-history provider is currently
        # backfilling LAST_SEASON. Do not attach those numbers
        # to CURRENT_SEASON.
        if market is not None:
            last["ats"] = (
                market.get(
                    "ats"
                )
            )

            last["over_under"] = (
                market.get(
                    "over_under"
                )
            )

        team_name = str(
            reference.get(
                "name"
            )
            or ""
        )

        if not team_name:
            team_name = str(
                current.get(
                    "team_name",
                    "",
                )
                or last.get(
                    "team_name",
                    "",
                )
                or team
            )

        teams.append(
            {
                "team": team,
                "team_name":
                    team_name,
                "conference":
                    reference.get(
                        "conference",
                        "",
                    ),
                "current_season":
                    current,
                "last_season":
                    last,
            }
        )

    return {
        "generated_at":
            utc_now_iso(),
        "league":
            "NBA",
        "current_season":
            CURRENT_SEASON,
        "last_season":
            LAST_SEASON,
        "season_type":
            SEASON_TYPE,
        "teams":
            teams,
    }


# ============================================================
# FALLBACK
# ============================================================

def republish_existing_output() -> bool:
    """
    If NBA Stats is unavailable, preserve the most recent
    valid team_stats.json instead of destroying site data.
    """

    existing = load_json(
        OUTPUT_FILE,
    )

    if existing is None:
        existing = load_json(
            WEB_OUTPUT_FILE,
        )

    if existing is None:
        return False

    teams = existing.get(
        "teams",
    )

    if not isinstance(
        teams,
        list,
    ):
        return False

    write_json(
        OUTPUT_FILE,
        existing,
    )

    write_json(
        WEB_OUTPUT_FILE,
        existing,
    )

    print(
        "NBA team stats API unavailable; "
        "republished last-known-good team_stats.json.",
        flush=True,
    )

    return True


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print(
        "\nBuilding NBA team statistics...",
        flush=True,
    )

    try:
        current_frame = (
            fetch_team_game_logs(
                CURRENT_SEASON,
            )
        )

        last_frame = (
            fetch_team_game_logs(
                LAST_SEASON,
            )
        )

    except Exception as exc:
        print(
            f"NBA team statistics fetch failed: {exc}",
            flush=True,
        )

        if republish_existing_output():
            return

        raise

    # --------------------------------------------------------
    # NBA TEAM STATISTICS
    # --------------------------------------------------------

    current_stats = (
        aggregate_team_season(
            current_frame,
            CURRENT_SEASON,
        )
    )

    last_stats = (
        aggregate_team_season(
            last_frame,
            LAST_SEASON,
        )
    )

    # --------------------------------------------------------
    # HISTORICAL CLOSING MARKETS
    # --------------------------------------------------------

    market_games = (
        load_market_history()
    )

    market_records = (
        build_market_records(
            market_games,
        )
    )

    # --------------------------------------------------------
    # FINAL PAYLOAD
    # --------------------------------------------------------

    payload = (
        build_team_payload(
            current_stats,
            last_stats,
            market_records,
        )
    )

    write_json(
        OUTPUT_FILE,
        payload,
    )

    write_json(
        WEB_OUTPUT_FILE,
        payload,
    )

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    current_with_games = sum(
        1
        for team in payload["teams"]
        if safe_int(
            team[
                "current_season"
            ]["games"]
        )
        > 0
    )

    last_with_games = sum(
        1
        for team in payload["teams"]
        if safe_int(
            team[
                "last_season"
            ]["games"]
        )
        > 0
    )

    teams_with_ats = sum(
        1
        for team in payload["teams"]
        if (
            team[
                "last_season"
            ].get(
                "ats"
            )
            is not None
        )
    )

    teams_with_totals = sum(
        1
        for team in payload["teams"]
        if (
            team[
                "last_season"
            ].get(
                "over_under"
            )
            is not None
        )
    )

    ats_games = sum(
        safe_int(
            (
                team[
                    "last_season"
                ].get(
                    "ats"
                )
                or {}
            ).get(
                "games_with_line",
                0,
            )
        )
        for team in payload[
            "teams"
        ]
    )

    total_games = sum(
        safe_int(
            (
                team[
                    "last_season"
                ].get(
                    "over_under"
                )
                or {}
            ).get(
                "games_with_total",
                0,
            )
        )
        for team in payload[
            "teams"
        ]
    )

    # Each completed game contributes one graded result
    # to each of its two teams.
    graded_spread_games = (
        ats_games // 2
    )

    graded_total_games = (
        total_games // 2
    )

    print(
        "\nNBA team statistics complete.",
        flush=True,
    )

    print(
        f"Teams:                     "
        f"{len(payload['teams']):,}",
        flush=True,
    )

    print(
        f"Current-season teams:      "
        f"{current_with_games:,}",
        flush=True,
    )

    print(
        f"Last-season teams:         "
        f"{last_with_games:,}",
        flush=True,
    )

    print(
        f"Teams with ATS data:       "
        f"{teams_with_ats:,}",
        flush=True,
    )

    print(
        f"Teams with O/U data:       "
        f"{teams_with_totals:,}",
        flush=True,
    )

    print(
        f"Graded spread games:       "
        f"{graded_spread_games:,}",
        flush=True,
    )

    print(
        f"Graded total games:        "
        f"{graded_total_games:,}",
        flush=True,
    )

    print(
        f"Model output:              "
        f"{OUTPUT_FILE}",
        flush=True,
    )

    print(
        f"Website output:            "
        f"{WEB_OUTPUT_FILE}",
        flush=True,
    )


if __name__ == "__main__":
    main()