from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import nflreadpy as nfl


# ============================================================
# PATHS / CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

MODEL_NFL_DIR = ROOT / "data" / "model" / "nfl"

WEB_ROOT = ROOT.parent / "alpha-wagerz-web"
WEB_NFL_DIR = WEB_ROOT / "public" / "data" / "nfl"

CURRENT_OUTPUT = MODEL_NFL_DIR / "team_rankings.json"
WEB_OUTPUT = WEB_NFL_DIR / "team_rankings.json"

CURRENT_SEASON = 2026


# ============================================================
# NFL STRUCTURE
# ============================================================

TEAM_STRUCTURE = {
    "ARI": ("NFC", "West"),
    "ATL": ("NFC", "South"),
    "BAL": ("AFC", "North"),
    "BUF": ("AFC", "East"),
    "CAR": ("NFC", "South"),
    "CHI": ("NFC", "North"),
    "CIN": ("AFC", "North"),
    "CLE": ("AFC", "North"),
    "DAL": ("NFC", "East"),
    "DEN": ("AFC", "West"),
    "DET": ("NFC", "North"),
    "GB": ("NFC", "North"),
    "HOU": ("AFC", "South"),
    "IND": ("AFC", "South"),
    "JAX": ("AFC", "South"),
    "KC": ("AFC", "West"),
    "LA": ("NFC", "West"),
    "LAC": ("AFC", "West"),
    "LV": ("AFC", "West"),
    "MIA": ("AFC", "East"),
    "MIN": ("NFC", "North"),
    "NE": ("AFC", "East"),
    "NO": ("NFC", "South"),
    "NYG": ("NFC", "East"),
    "NYJ": ("AFC", "East"),
    "PHI": ("NFC", "East"),
    "PIT": ("AFC", "North"),
    "SEA": ("NFC", "West"),
    "SF": ("NFC", "West"),
    "TB": ("NFC", "South"),
    "TEN": ("AFC", "South"),
    "WAS": ("NFC", "East"),
}


# ============================================================
# HELPERS
# ============================================================

def _rows(frame: Any) -> list[dict[str, Any]]:
    """
    Convert nflreadpy Polars/Pandas-like results into dictionaries.
    """

    if frame is None:
        return []

    if hasattr(frame, "to_dicts"):
        return frame.to_dicts()

    if hasattr(frame, "to_dict"):
        try:
            records = frame.to_dict(orient="records")
            if isinstance(records, list):
                return records
        except TypeError:
            pass

    return []


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default

        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default

        return int(float(value))
    except (TypeError, ValueError):
        return default


def _round(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def _safe_div(
    numerator: float,
    denominator: float,
    digits: int = 2,
) -> float | None:
    if denominator <= 0:
        return None

    return _round(numerator / denominator, digits)


def _normalize_team(value: Any) -> str:
    team = str(value or "").strip().upper()

    aliases = {
        "JAC": "JAX",
        "LAR": "LA",
        "STL": "LA",
        "OAK": "LV",
        "SD": "LAC",
        "SDG": "LAC",
    }

    return aliases.get(team, team)


def _same_division(team_a: str, team_b: str) -> bool:
    a = TEAM_STRUCTURE.get(team_a)
    b = TEAM_STRUCTURE.get(team_b)

    return bool(
        a
        and b
        and a[0] == b[0]
        and a[1] == b[1]
    )


def _same_conference(team_a: str, team_b: str) -> bool:
    a = TEAM_STRUCTURE.get(team_a)
    b = TEAM_STRUCTURE.get(team_b)

    return bool(a and b and a[0] == b[0])


def _record_text(
    wins: int,
    losses: int,
    ties: int = 0,
) -> str:
    if ties:
        return f"{wins}-{losses}-{ties}"

    return f"{wins}-{losses}"


def _empty_split_record() -> dict[str, int]:
    return {
        "wins": 0,
        "losses": 0,
        "ties": 0,
    }


def _update_split_record(
    record: dict[str, int],
    result: str,
) -> None:
    if result == "W":
        record["wins"] += 1
    elif result == "L":
        record["losses"] += 1
    elif result == "T":
        record["ties"] += 1


def _result(
    points_for: float,
    points_against: float,
) -> str:
    if points_for > points_against:
        return "W"

    if points_for < points_against:
        return "L"

    return "T"


def _finished_regular_game(row: dict[str, Any]) -> bool:
    """
    Only completed 2026 REG games count toward standings/stats.
    """

    season = _int(row.get("season"))
    game_type = str(
        row.get("game_type")
        or row.get("season_type")
        or ""
    ).upper()

    if season != CURRENT_SEASON:
        return False

    if game_type not in {"REG", "REGULAR"}:
        return False

    away_score = row.get("away_score")
    home_score = row.get("home_score")

    if away_score is None or home_score is None:
        return False

    return True


# ============================================================
# TEAM CONTAINERS
# ============================================================

def _new_team(team: str) -> dict[str, Any]:
    conference, division = TEAM_STRUCTURE[team]

    return {
        "team": team,
        "conference": conference,
        "division": division,

        "_games": 0,

        "_wins": 0,
        "_losses": 0,
        "_ties": 0,

        "_home": _empty_split_record(),
        "_away": _empty_split_record(),
        "_division": _empty_split_record(),
        "_conference": _empty_split_record(),

        "_results": [],

        "_points_for": 0.0,
        "_points_against": 0.0,

        "_offensive_touchdowns": 0.0,
        "_field_goals": 0.0,

        "_rush_attempts": 0.0,
        "_rush_yards": 0.0,

        "_receptions": 0.0,
        "_receiving_yards": 0.0,
        "_passing_yards": 0.0,

        "_offensive_plays": 0.0,
        "_total_yards": 0.0,
        "_turnovers": 0.0,

        "_touchdowns_allowed": 0.0,
        "_field_goals_allowed": 0.0,

        "_rush_attempts_allowed": 0.0,
        "_rush_yards_allowed": 0.0,

        "_receptions_allowed": 0.0,
        "_receiving_yards_allowed": 0.0,
        "_passing_yards_allowed": 0.0,

        "_plays_allowed": 0.0,
        "_total_yards_allowed": 0.0,
        "_takeaways": 0.0,
    }


# ============================================================
# STANDINGS
# ============================================================

def _apply_schedule(
    teams: dict[str, dict[str, Any]],
    schedule_rows: list[dict[str, Any]],
) -> set[str]:
    """
    Apply completed regular-season games to records and scoring.

    Returns the game_ids that count toward 2026 regular-season
    team statistics.
    """

    completed_game_ids: set[str] = set()

    finished_games = [
        row
        for row in schedule_rows
        if _finished_regular_game(row)
    ]

    finished_games.sort(
        key=lambda row: (
            str(row.get("gameday") or row.get("game_date") or ""),
            str(row.get("gametime") or row.get("game_time") or ""),
        )
    )

    for row in finished_games:
        away = _normalize_team(
            row.get("away_team")
        )
        home = _normalize_team(
            row.get("home_team")
        )

        if away not in teams or home not in teams:
            continue

        away_score = _num(
            row.get("away_score")
        )
        home_score = _num(
            row.get("home_score")
        )

        game_id = str(
            row.get("game_id") or ""
        ).strip()

        if game_id:
            completed_game_ids.add(game_id)

        away_result = _result(
            away_score,
            home_score,
        )
        home_result = _result(
            home_score,
            away_score,
        )

        away_team = teams[away]
        home_team = teams[home]

        away_team["_games"] += 1
        home_team["_games"] += 1

        away_team["_points_for"] += away_score
        away_team["_points_against"] += home_score

        home_team["_points_for"] += home_score
        home_team["_points_against"] += away_score

        if away_result == "W":
            away_team["_wins"] += 1
        elif away_result == "L":
            away_team["_losses"] += 1
        else:
            away_team["_ties"] += 1

        if home_result == "W":
            home_team["_wins"] += 1
        elif home_result == "L":
            home_team["_losses"] += 1
        else:
            home_team["_ties"] += 1

        _update_split_record(
            away_team["_away"],
            away_result,
        )
        _update_split_record(
            home_team["_home"],
            home_result,
        )

        if _same_division(away, home):
            _update_split_record(
                away_team["_division"],
                away_result,
            )
            _update_split_record(
                home_team["_division"],
                home_result,
            )

        if _same_conference(away, home):
            _update_split_record(
                away_team["_conference"],
                away_result,
            )
            _update_split_record(
                home_team["_conference"],
                home_result,
            )

        away_team["_results"].append(
            away_result
        )
        home_team["_results"].append(
            home_result
        )

    return completed_game_ids


# ============================================================
# PLAY-BY-PLAY STATISTICS
# ============================================================

def _pbp_team(row: dict[str, Any], key: str) -> str:
    return _normalize_team(row.get(key))


def _apply_pbp(
    teams: dict[str, dict[str, Any]],
    pbp_rows: list[dict[str, Any]],
    completed_game_ids: set[str],
) -> None:
    """
    Build team offense and defense totals from 2026 regular-season
    play-by-play.

    Only game_ids already confirmed as completed REG games by the
    schedule are counted.
    """

    for row in pbp_rows:
        game_id = str(
            row.get("game_id") or ""
        ).strip()

        if game_id not in completed_game_ids:
            continue

        posteam = _pbp_team(
            row,
            "posteam",
        )
        defteam = _pbp_team(
            row,
            "defteam",
        )

        if (
            posteam not in teams
            or defteam not in teams
        ):
            continue

        offense = teams[posteam]
        defense = teams[defteam]

        play_type = str(
            row.get("play_type") or ""
        ).lower()

        pass_attempt = _num(
            row.get("pass_attempt")
        )
        rush_attempt = _num(
            row.get("rush_attempt")
        )

        complete_pass = _num(
            row.get("complete_pass")
        )

        passing_yards = _num(
            row.get("passing_yards")
        )
        receiving_yards = _num(
            row.get("receiving_yards")
        )
        rushing_yards = _num(
            row.get("rushing_yards")
        )

        touchdown = _num(
            row.get("touchdown")
        )

        pass_touchdown = _num(
            row.get("pass_touchdown")
        )
        rush_touchdown = _num(
            row.get("rush_touchdown")
        )

        field_goal_result = str(
            row.get("field_goal_result")
            or ""
        ).lower()

        interception = _num(
            row.get("interception")
        )
        fumble_lost = _num(
            row.get("fumble_lost")
        )

        # ----------------------------------------------------
        # Offensive plays
        # ----------------------------------------------------

        if pass_attempt > 0 or rush_attempt > 0:
            offense["_offensive_plays"] += 1
            defense["_plays_allowed"] += 1

        # ----------------------------------------------------
        # Rushing
        # ----------------------------------------------------

        if rush_attempt > 0:
            offense["_rush_attempts"] += 1
            defense["_rush_attempts_allowed"] += 1

            offense["_rush_yards"] += rushing_yards
            defense["_rush_yards_allowed"] += rushing_yards

        # ----------------------------------------------------
        # Passing / receptions
        # ----------------------------------------------------

        if complete_pass > 0:
            offense["_receptions"] += 1
            defense["_receptions_allowed"] += 1

        if pass_attempt > 0:
            offense["_passing_yards"] += passing_yards
            defense["_passing_yards_allowed"] += passing_yards

        if complete_pass > 0:
            offense["_receiving_yards"] += receiving_yards
            defense["_receiving_yards_allowed"] += receiving_yards

        # ----------------------------------------------------
        # Total yards
        # ----------------------------------------------------

        play_yards = 0.0

        if rush_attempt > 0:
            play_yards = rushing_yards
        elif pass_attempt > 0:
            play_yards = passing_yards

        offense["_total_yards"] += play_yards
        defense["_total_yards_allowed"] += play_yards

        # ----------------------------------------------------
        # Offensive touchdowns
        #
        # Count passing/rushing offensive TDs only.
        # This deliberately excludes defensive and return TDs.
        # ----------------------------------------------------

        offensive_td = (
            pass_touchdown > 0
            or rush_touchdown > 0
        )

        if offensive_td:
            offense["_offensive_touchdowns"] += 1
            defense["_touchdowns_allowed"] += 1

        # Fallback for datasets where pass/rush TD flags may be
        # absent but the play is clearly an offensive TD.
        elif (
            touchdown > 0
            and play_type in {
                "pass",
                "run",
                "qb_kneel",
            }
        ):
            offense["_offensive_touchdowns"] += 1
            defense["_touchdowns_allowed"] += 1

        # ----------------------------------------------------
        # Field goals made
        # ----------------------------------------------------

        if field_goal_result == "made":
            offense["_field_goals"] += 1
            defense["_field_goals_allowed"] += 1

        # ----------------------------------------------------
        # Turnovers
        # ----------------------------------------------------

        turnover = (
            interception > 0
            or fumble_lost > 0
        )

        if turnover:
            offense["_turnovers"] += 1
            defense["_takeaways"] += 1


# ============================================================
# FINALIZE STATISTICS
# ============================================================

def _streak(results: list[str]) -> str:
    if not results:
        return "—"

    latest = results[-1]

    count = 0

    for result in reversed(results):
        if result != latest:
            break

        count += 1

    return f"{latest}{count}"


def _split_text(
    record: dict[str, int],
) -> str:
    return _record_text(
        record["wins"],
        record["losses"],
        record["ties"],
    )


def _finalize_team(
    raw: dict[str, Any],
) -> dict[str, Any]:
    games = raw["_games"]

    wins = raw["_wins"]
    losses = raw["_losses"]
    ties = raw["_ties"]

    win_pct = None

    if games > 0:
        win_pct = _round(
            (wins + (0.5 * ties))
            / games,
            3,
        )

    standings = {
        "games_played": games,

        "wins": wins,
        "losses": losses,
        "ties": ties,

        "record": _record_text(
            wins,
            losses,
            ties,
        ),

        "win_pct": win_pct,

        "nfl_rank": None,
        "conference_rank": None,
        "division_rank": None,

        "points_for": _round(
            raw["_points_for"],
            0,
        ),
        "points_against": _round(
            raw["_points_against"],
            0,
        ),

        "point_differential": _round(
            raw["_points_for"]
            - raw["_points_against"],
            0,
        ),

        "home_record": _split_text(
            raw["_home"]
        ),
        "away_record": _split_text(
            raw["_away"]
        ),
        "division_record": _split_text(
            raw["_division"]
        ),
        "conference_record": _split_text(
            raw["_conference"]
        ),

        "streak": _streak(
            raw["_results"]
        ),
    }

    offense = {
        "points_per_game": _safe_div(
            raw["_points_for"],
            games,
        ),

        "td_per_game": _safe_div(
            raw["_offensive_touchdowns"],
            games,
        ),

        "field_goals_per_game": _safe_div(
            raw["_field_goals"],
            games,
        ),

        "rush_attempts_per_game": _safe_div(
            raw["_rush_attempts"],
            games,
        ),

        "rush_yards_per_game": _safe_div(
            raw["_rush_yards"],
            games,
        ),

        "receptions_per_game": _safe_div(
            raw["_receptions"],
            games,
        ),

        "receiving_yards_per_game": _safe_div(
            raw["_receiving_yards"],
            games,
        ),

        "passing_yards_per_game": _safe_div(
            raw["_passing_yards"],
            games,
        ),

        "total_yards_per_game": _safe_div(
            raw["_total_yards"],
            games,
        ),

        "yards_per_play": _safe_div(
            raw["_total_yards"],
            raw["_offensive_plays"],
        ),

        "turnovers_per_game": _safe_div(
            raw["_turnovers"],
            games,
        ),
    }

    defense = {
        "points_allowed_per_game": _safe_div(
            raw["_points_against"],
            games,
        ),

        "td_allowed_per_game": _safe_div(
            raw["_touchdowns_allowed"],
            games,
        ),

        "field_goals_allowed_per_game": _safe_div(
            raw["_field_goals_allowed"],
            games,
        ),

        "rush_attempts_allowed_per_game": _safe_div(
            raw["_rush_attempts_allowed"],
            games,
        ),

        "rush_yards_allowed_per_game": _safe_div(
            raw["_rush_yards_allowed"],
            games,
        ),

        "receptions_allowed_per_game": _safe_div(
            raw["_receptions_allowed"],
            games,
        ),

        "receiving_yards_allowed_per_game": _safe_div(
            raw["_receiving_yards_allowed"],
            games,
        ),

        "passing_yards_allowed_per_game": _safe_div(
            raw["_passing_yards_allowed"],
            games,
        ),

        "total_yards_allowed_per_game": _safe_div(
            raw["_total_yards_allowed"],
            games,
        ),

        "yards_per_play_allowed": _safe_div(
            raw["_total_yards_allowed"],
            raw["_plays_allowed"],
        ),

        "takeaways_per_game": _safe_div(
            raw["_takeaways"],
            games,
        ),
    }

    return {
        "team": raw["team"],
        "conference": raw["conference"],
        "division": raw["division"],
        "standings": standings,
        "offense": offense,
        "defense": defense,
        "ranks": {
            "offense": {},
            "defense": {},
        },
    }


# ============================================================
# RANKING HELPERS
# ============================================================

def _standing_sort_key(
    team: dict[str, Any],
) -> tuple:
    standings = team["standings"]

    games = standings["games_played"]

    # Before games are played, keep teams alphabetically stable.
    if games <= 0:
        return (
            1,
            0,
            0,
            0,
            team["team"],
        )

    win_pct = (
        standings["win_pct"]
        if standings["win_pct"] is not None
        else -1
    )

    return (
        0,
        -win_pct,
        -standings["point_differential"],
        -standings["points_for"],
        team["team"],
    )


def _assign_standing_ranks(
    teams: list[dict[str, Any]],
) -> None:
    # NFL-wide
    ordered = sorted(
        teams,
        key=_standing_sort_key,
    )

    for rank, team in enumerate(
        ordered,
        start=1,
    ):
        if team["standings"]["games_played"] > 0:
            team["standings"]["nfl_rank"] = rank

    # Conference
    for conference in ("AFC", "NFC"):
        conference_teams = [
            team
            for team in teams
            if team["conference"] == conference
        ]

        conference_teams.sort(
            key=_standing_sort_key
        )

        for rank, team in enumerate(
            conference_teams,
            start=1,
        ):
            if team["standings"]["games_played"] > 0:
                team["standings"]["conference_rank"] = rank

    # Division
    for conference in ("AFC", "NFC"):
        for division in (
            "East",
            "North",
            "South",
            "West",
        ):
            division_teams = [
                team
                for team in teams
                if (
                    team["conference"] == conference
                    and team["division"] == division
                )
            ]

            division_teams.sort(
                key=_standing_sort_key
            )

            for rank, team in enumerate(
                division_teams,
                start=1,
            ):
                if team["standings"]["games_played"] > 0:
                    team["standings"]["division_rank"] = rank


OFFENSE_RANK_DIRECTIONS = {
    "points_per_game": "desc",
    "td_per_game": "desc",
    "field_goals_per_game": "desc",
    "rush_attempts_per_game": "desc",
    "rush_yards_per_game": "desc",
    "receptions_per_game": "desc",
    "receiving_yards_per_game": "desc",
    "passing_yards_per_game": "desc",
    "total_yards_per_game": "desc",
    "yards_per_play": "desc",
    "turnovers_per_game": "asc",
}

DEFENSE_RANK_DIRECTIONS = {
    "points_allowed_per_game": "asc",
    "td_allowed_per_game": "asc",
    "field_goals_allowed_per_game": "asc",
    "rush_attempts_allowed_per_game": "asc",
    "rush_yards_allowed_per_game": "asc",
    "receptions_allowed_per_game": "asc",
    "receiving_yards_allowed_per_game": "asc",
    "passing_yards_allowed_per_game": "asc",
    "total_yards_allowed_per_game": "asc",
    "yards_per_play_allowed": "asc",
    "takeaways_per_game": "desc",
}


def _assign_metric_ranks(
    teams: list[dict[str, Any]],
    section: str,
    directions: dict[str, str],
) -> None:
    for metric, direction in directions.items():
        eligible = [
            team
            for team in teams
            if (
                team["standings"]["games_played"] > 0
                and team[section].get(metric)
                is not None
            )
        ]

        eligible.sort(
            key=lambda team: (
                team[section][metric]
                if direction == "asc"
                else -team[section][metric],
                team["team"],
            )
        )

        for rank, team in enumerate(
            eligible,
            start=1,
        ):
            team["ranks"][section][metric] = rank


# ============================================================
# BUILD
# ============================================================

def build_nfl_team_rankings() -> dict[str, Any]:
    print("\n🏈 NFL Team Rankings / Season Stats")

    teams = {
        team: _new_team(team)
        for team in TEAM_STRUCTURE
    }

    print("   Loading NFL schedule...")

    schedules = nfl.load_schedules(
        seasons=[CURRENT_SEASON]
    )

    schedule_rows = _rows(
        schedules
    )

    completed_game_ids = _apply_schedule(
        teams,
        schedule_rows,
    )

    print(
        f"   Completed 2026 REG games: "
        f"{len(completed_game_ids)}"
    )

    pbp_rows: list[dict[str, Any]] = []

    if completed_game_ids:
        print(
            "   Loading 2026 play-by-play..."
        )

        pbp = nfl.load_pbp(
            seasons=[CURRENT_SEASON]
        )

        pbp_rows = _rows(
            pbp
        )

        _apply_pbp(
            teams,
            pbp_rows,
            completed_game_ids,
        )
    else:
        print(
            "   Regular season has not "
            "started — season averages "
            "will remain empty."
        )

    final_teams = [
        _finalize_team(team)
        for team in teams.values()
    ]

    _assign_standing_ranks(
        final_teams
    )

    _assign_metric_ranks(
        final_teams,
        "offense",
        OFFENSE_RANK_DIRECTIONS,
    )

    _assign_metric_ranks(
        final_teams,
        "defense",
        DEFENSE_RANK_DIRECTIONS,
    )

    final_teams.sort(
        key=lambda team: (
            team["conference"],
            team["division"],
            team["team"],
        )
    )

    payload = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "season": CURRENT_SEASON,
        "season_type": "REG",

        "completed_games": len(
            completed_game_ids
        ),

        "teams": final_teams,
    }

    CURRENT_OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    CURRENT_OUTPUT.write_text(
        json.dumps(
            payload,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        f"   ✓ Model: {CURRENT_OUTPUT}"
    )

    # Only write the web copy when that directory exists.
    if WEB_NFL_DIR.exists():
        WEB_OUTPUT.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        WEB_OUTPUT.write_text(
            json.dumps(
                payload,
                indent=2,
            ),
            encoding="utf-8",
        )

        print(
            f"   ✓ Web:   {WEB_OUTPUT}"
        )

    print(
        f"   ✓ {len(final_teams)} teams"
    )

    return payload


if __name__ == "__main__":
    build_nfl_team_rankings()