from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import nflreadpy as nfl

from utils.json_utils import save_json


MODEL_ROOT = Path(__file__).resolve().parents[1]

MODEL_OUTPUT_DIR = (
    MODEL_ROOT
    / "data"
    / "processed"
    / "nfl"
)

WEB_OUTPUT_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nfl"
)

CURRENT_SEASON = 2026

CAREER_START_SEASON = 2016


def clean_value(value: Any):
    if value is None:
        return ""

    try:
        if value != value:
            return ""
    except Exception:
        pass

    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass

    # Convert Python date/datetime values to JSON-safe strings.
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass

    return value


def clean_record(
    row: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: clean_value(value)
        for key, value in row.items()
    }


def polars_records(frame) -> list[dict[str, Any]]:
    if frame is None:
        return []

    try:
        rows = frame.to_dicts()
    except Exception:
        return []

    return [
        clean_record(row)
        for row in rows
    ]


def write_output(
    filename: str,
    payload: Any,
):
    MODEL_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    WEB_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    model_file = (
        MODEL_OUTPUT_DIR
        / filename
    )

    web_file = (
        WEB_OUTPUT_DIR
        / filename
    )

    save_json(
        payload,
        model_file,
    )

    save_json(
        payload,
        web_file,
    )

    print(
        f"✅ {filename}"
    )

    print(
        f"   model: {model_file}"
    )

    print(
        f"   web:   {web_file}"
    )


def get_first(
    row: dict[str, Any],
    *keys: str,
    default="",
):
    for key in keys:
        value = row.get(key)

        if value not in (
            None,
            "",
        ):
            return value

    return default


def normalize_team(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip().upper()


def normalize_position(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip().upper()


def build_teams():
    print(
        "🏈 Loading NFL teams..."
    )

    frame = nfl.load_teams()

    rows = polars_records(
        frame
    )

    teams = []

    for row in rows:
        team = {
            "abbr": get_first(
                row,
                "team_abbr",
                "team",
            ),
            "name": get_first(
                row,
                "team_name",
                "team_nick",
                "team",
            ),
            "short_name": get_first(
                row,
                "team_name",
                "team_nick",
            ),
            "conference": get_first(
                row,
                "team_conf",
                "conference",
            ),
            "division": get_first(
                row,
                "team_division",
                "division",
            ),
            "logo": get_first(
                row,
                "team_logo_espn",
                "team_logo_wikipedia",
                "team_logo",
            ),
            "wordmark": get_first(
                row,
                "team_wordmark",
            ),
            "color": get_first(
                row,
                "team_color",
            ),
            "color2": get_first(
                row,
                "team_color2",
            ),
        }

        if team["abbr"]:
            teams.append(team)

    write_output(
        "teams.json",
        teams,
    )

    return teams


def build_rosters():
    print(
        "🏈 Loading NFL rosters..."
    )

    frame = nfl.load_rosters(
        [CURRENT_SEASON]
    )

    rows = polars_records(
        frame
    )

    roster = []

    for row in rows:
        player = {
            "season": get_first(
                row,
                "season",
                default=CURRENT_SEASON,
            ),
            "player_id": get_first(
                row,
                "gsis_id",
                "player_id",
            ),
            "espn_id": get_first(
                row,
                "espn_id",
            ),
            "pfr_id": get_first(
                row,
                "pfr_id",
            ),
            "team": normalize_team(
                get_first(
                    row,
                    "team",
                    "team_abbr",
                )
            ),
            "player": get_first(
                row,
                "full_name",
                "football_name",
                "player_name",
            ),
            "first_name": get_first(
                row,
                "first_name",
            ),
            "last_name": get_first(
                row,
                "last_name",
            ),
            "position": normalize_position(
                get_first(
                    row,
                    "position",
                    "depth_chart_position",
                )
            ),
            "depth_chart_position": normalize_position(
                get_first(
                    row,
                    "depth_chart_position",
                )
            ),
            "status": get_first(
                row,
                "status",
            ),
            "jersey_number": get_first(
                row,
                "jersey_number",
            ),
            "height": get_first(
                row,
                "height",
            ),
            "weight": get_first(
                row,
                "weight",
            ),
            "birth_date": get_first(
                row,
                "birth_date",
            ),
            "college": get_first(
                row,
                "college",
            ),
            "years_exp": get_first(
                row,
                "years_exp",
            ),
            "headshot_url": get_first(
                row,
                "headshot_url",
            ),
        }

        if (
            player["player"]
            and player["team"]
        ):
            roster.append(
                player
            )

    roster.sort(
        key=lambda player: (
            player["team"],
            player["position"],
            player["player"],
        )
    )

    write_output(
        "rosters.json",
        roster,
    )

    return roster


def load_current_player_stats():
    seasons_to_try = [
        CURRENT_SEASON,
        CURRENT_SEASON - 1,
    ]

    for season in seasons_to_try:
        try:
            print(
                f"   Trying {season} player stats..."
            )

            frame = nfl.load_player_stats(
                [season]
            )

            rows = polars_records(
                frame
            )

            if rows:
                print(
                    f"   ✅ Using {season} player stats "
                    f"({len(rows)} rows)"
                )

                # IMPORTANT:
                # Return the flat list of dictionaries directly.
                return rows, season

        except Exception as exc:
            print(
                f"   ⚠️ {season} stats unavailable: {exc}"
            )

    return [], CURRENT_SEASON


def build_season_stats():
    print(
        "🏈 Loading current NFL player stats..."
    )

    rows, stats_season = load_current_player_stats()

    players: dict[
        tuple[str, str],
        dict[str, Any],
    ] = {}

    for row in rows:
        season_type = str(
            get_first(
                row,
                "season_type",
                default="REG",
            )
        ).upper()

        if season_type not in {
            "REG",
            "",
        }:
            continue

        player_id = str(
            get_first(
                row,
                "player_id",
                "gsis_id",
            )
        )

        player_name = get_first(
            row,
            "player_display_name",
            "player_name",
            "name",
        )

        team = normalize_team(
            get_first(
                row,
                "recent_team",
                "team",
            )
        )

        position = normalize_position(
            get_first(
                row,
                "position",
            )
        )

        if not player_name:
            continue

        key = (
            player_id or player_name,
            team,
        )

        player = players.setdefault(
            key,
            {
                "season": stats_season,
                "player_id": player_id,
                "player": player_name,
                "team": team,
                "position": position,
                "games": 0,

                "passing": {
                    "completions": 0,
                    "attempts": 0,
                    "yards": 0,
                    "tds": 0,
                    "interceptions": 0,
                },

                "rushing": {
                    "carries": 0,
                    "yards": 0,
                    "tds": 0,
                },

                "receiving": {
                    "targets": 0,
                    "receptions": 0,
                    "yards": 0,
                    "tds": 0,
                },

                "fantasy": {
                    "points": 0,
                    "ppr_points": 0,
                },
            },
        )

        player["games"] += 1

        player["passing"]["completions"] += float(
            get_first(
                row,
                "completions",
                default=0,
            )
            or 0
        )

        player["passing"]["attempts"] += float(
            get_first(
                row,
                "attempts",
                "passing_attempts",
                default=0,
            )
            or 0
        )

        player["passing"]["yards"] += float(
            get_first(
                row,
                "passing_yards",
                default=0,
            )
            or 0
        )

        player["passing"]["tds"] += float(
            get_first(
                row,
                "passing_tds",
                default=0,
            )
            or 0
        )

        player["passing"]["interceptions"] += float(
            get_first(
                row,
                "interceptions",
                default=0,
            )
            or 0
        )

        player["rushing"]["carries"] += float(
            get_first(
                row,
                "carries",
                "rushing_attempts",
                default=0,
            )
            or 0
        )

        player["rushing"]["yards"] += float(
            get_first(
                row,
                "rushing_yards",
                default=0,
            )
            or 0
        )

        player["rushing"]["tds"] += float(
            get_first(
                row,
                "rushing_tds",
                default=0,
            )
            or 0
        )

        player["receiving"]["targets"] += float(
            get_first(
                row,
                "targets",
                default=0,
            )
            or 0
        )

        player["receiving"]["receptions"] += float(
            get_first(
                row,
                "receptions",
                default=0,
            )
            or 0
        )

        player["receiving"]["yards"] += float(
            get_first(
                row,
                "receiving_yards",
                default=0,
            )
            or 0
        )

        player["receiving"]["tds"] += float(
            get_first(
                row,
                "receiving_tds",
                default=0,
            )
            or 0
        )

        player["fantasy"]["points"] += float(
            get_first(
                row,
                "fantasy_points",
                default=0,
            )
            or 0
        )

        player["fantasy"]["ppr_points"] += float(
            get_first(
                row,
                "fantasy_points_ppr",
                default=0,
            )
            or 0
        )

    output = []

    for player in players.values():
        games = max(
            1,
            int(
                player["games"]
            ),
        )

        player["averages"] = {
            "passing_yards": round(
                player["passing"]["yards"]
                / games,
                1,
            ),
            "passing_tds": round(
                player["passing"]["tds"]
                / games,
                2,
            ),
            "interceptions": round(
                player["passing"]["interceptions"]
                / games,
                2,
            ),
            "carries": round(
                player["rushing"]["carries"]
                / games,
                1,
            ),
            "rushing_yards": round(
                player["rushing"]["yards"]
                / games,
                1,
            ),
            "rushing_tds": round(
                player["rushing"]["tds"]
                / games,
                2,
            ),
            "targets": round(
                player["receiving"]["targets"]
                / games,
                1,
            ),
            "receptions": round(
                player["receiving"]["receptions"]
                / games,
                1,
            ),
            "receiving_yards": round(
                player["receiving"]["yards"]
                / games,
                1,
            ),
            "receiving_tds": round(
                player["receiving"]["tds"]
                / games,
                2,
            ),
            "fantasy_points": round(
                player["fantasy"]["points"]
                / games,
                1,
            ),
            "fantasy_points_ppr": round(
                player["fantasy"]["ppr_points"]
                / games,
                1,
            ),
        }

        output.append(
            player
        )

    output.sort(
        key=lambda player: (
            player["team"],
            player["position"],
            player["player"],
        )
    )

    write_output(
        "player_stats.json",
        output,
    )

    return output


def build_career_stats():
    print(
        "🏈 Loading NFL career history..."
    )

    seasons = list(
        range(
            CAREER_START_SEASON,
            CURRENT_SEASON + 1,
        )
    )

    rows = []

    for season in seasons:
        try:
            print(
                f"   Loading {season} player stats..."
            )

            frame = nfl.load_player_stats(
                [season]
            )

            season_rows = polars_records(
                frame
            )

            rows.extend(
                season_rows
            )

            print(
                f"   ✅ {season}: {len(season_rows)} rows"
            )

        except Exception as exc:
            print(
                f"   ⚠️ {season} unavailable: {exc}"
            )

    players: dict[
        str,
        dict[str, Any],
    ] = {}

    for row in rows:
        season_type = str(
            get_first(
                row,
                "season_type",
                default="REG",
            )
        ).upper()

        if season_type not in {
            "REG",
            "",
        }:
            continue

        player_id = str(
            get_first(
                row,
                "player_id",
                "gsis_id",
            )
        )

        player_name = get_first(
            row,
            "player_display_name",
            "player_name",
            "name",
        )

        if not player_name:
            continue

        key = (
            player_id
            or player_name
        )

        player = players.setdefault(
            key,
            {
                "player_id": player_id,
                "player": player_name,
                "position": normalize_position(
                    get_first(
                        row,
                        "position",
                    )
                ),
                "seasons": {},
            },
        )

        season = str(
            get_first(
                row,
                "season",
            )
        )

        season_data = (
            player["seasons"]
            .setdefault(
                season,
                {
                    "games": 0,

                    "completions": 0,
                    "attempts": 0,
                    "passing_yards": 0,
                    "passing_tds": 0,
                    "interceptions": 0,

                    "carries": 0,
                    "rushing_yards": 0,
                    "rushing_tds": 0,

                    "targets": 0,
                    "receptions": 0,
                    "receiving_yards": 0,
                    "receiving_tds": 0,

                    "fantasy_points": 0,
                    "fantasy_points_ppr": 0,
                },
            )
        )

        season_data["games"] += 1

        for field, aliases in {
    "completions": (
        "completions",
    ),
    "attempts": (
        "attempts",
        "passing_attempts",
    ),
    "passing_yards": (
        "passing_yards",
    ),
    "passing_tds": (
        "passing_tds",
    ),
    "interceptions": (
        "interceptions",
    ),
            "carries": (
                "carries",
                "rushing_attempts",
            ),
            "rushing_yards": (
                "rushing_yards",
            ),
            "rushing_tds": (
                "rushing_tds",
            ),
            "targets": (
                "targets",
            ),
            "receptions": (
                "receptions",
            ),
            "receiving_yards": (
                "receiving_yards",
            ),
            "receiving_tds": (
                "receiving_tds",
            ),
            "fantasy_points": (
                "fantasy_points",
            ),
            "fantasy_points_ppr": (
                "fantasy_points_ppr",
            ),
        }.items():
            season_data[field] += float(
                get_first(
                    row,
                    *aliases,
                    default=0,
                )
                or 0
            )

    output = []

    for player in players.values():
        career_totals = {
            "games": 0,
            "completions": 0,
            "attempts": 0,
            "passing_yards": 0,
            "passing_tds": 0,
            "interceptions": 0,
            "carries": 0,
            "rushing_yards": 0,
            "rushing_tds": 0,
            "targets": 0,
            "receptions": 0,
            "receiving_yards": 0,
            "receiving_tds": 0,
            "fantasy_points": 0,
            "fantasy_points_ppr": 0,
        }

        season_rows = []

        for season, data in sorted(
            player["seasons"].items()
        ):
            games = max(
                1,
                int(
                    data["games"]
                ),
            )

            season_row = {
                "season": int(
                    season
                ),
                "totals": data,
                "averages": {
                    field: round(
                        value / games,
                        2,
                    )
                    for field, value
                    in data.items()
                    if field != "games"
                },
            }

            season_rows.append(
                season_row
            )

            for field in career_totals:
                career_totals[field] += data.get(
                    field,
                    0,
                )

        games = max(
            1,
            int(
                career_totals[
                    "games"
                ]
            ),
        )

        output.append(
            {
                "player_id": player[
                    "player_id"
                ],
                "player": player[
                    "player"
                ],
                "position": player[
                    "position"
                ],
                "career_totals": (
                    career_totals
                ),
                "career_averages": {
                    field: round(
                        value / games,
                        2,
                    )
                    for field, value
                    in career_totals.items()
                    if field != "games"
                },
                "seasons": season_rows,
            }
        )

    write_output(
        "career_stats.json",
        output,
    )

    return output


def build_schedule():
    print(
        "🏈 Loading NFL schedule..."
    )

    frame = nfl.load_schedules(
        [CURRENT_SEASON]
    )

    rows = polars_records(
        frame
    )

    games = []

    for row in rows:
        game = {
            "game_id": get_first(
                row,
                "game_id",
                "old_game_id",
                "gsis",
            ),
            "season": get_first(
                row,
                "season",
                default=CURRENT_SEASON,
            ),
            "week": get_first(
                row,
                "week",
            ),
            "game_type": get_first(
                row,
                "game_type",
            ),
            "game_date": get_first(
                row,
                "gameday",
                "game_date",
            ),
            "game_time": get_first(
                row,
                "gametime",
                "game_time",
            ),
            "away_team": normalize_team(
                get_first(
                    row,
                    "away_team",
                )
            ),
            "home_team": normalize_team(
                get_first(
                    row,
                    "home_team",
                )
            ),
            "venue": get_first(
                row,
                "stadium",
                "stadium_name",
            ),
            "roof": get_first(
                row,
                "roof",
            ),
            "surface": get_first(
                row,
                "surface",
            ),
            "temperature": get_first(
                row,
                "temp",
            ),
            "wind": get_first(
                row,
                "wind",
            ),
            "spread_line": get_first(
                row,
                "spread_line",
            ),
            "total_line": get_first(
                row,
                "total_line",
            ),
            "away_moneyline": get_first(
                row,
                "away_moneyline",
            ),
            "home_moneyline": get_first(
                row,
                "home_moneyline",
            ),
        }

        game["game"] = (
            f'{game["away_team"]} @ '
            f'{game["home_team"]}'
        )

        if (
            game["game_id"]
            and game["away_team"]
            and game["home_team"]
        ):
            games.append(
                game
            )

    games.sort(
        key=lambda game: (
            str(
                game["game_date"]
            ),
            str(
                game["game_time"]
            ),
        )
    )

    write_output(
        "schedule.json",
        games,
    )

    return games


def valid_game_date(
    value: Any,
):
    text = str(
        value or ""
    ).strip()

    if not text:
        return None

    try:
        return date.fromisoformat(
            text[:10]
        )
    except Exception:
        return None


def build_slates(
    schedule: list[dict[str, Any]],
):
    today = date.today()

    future_games = [
        game
        for game in schedule
        if (
            valid_game_date(
                game.get(
                    "game_date"
                )
            )
            is not None
            and valid_game_date(
                game.get(
                    "game_date"
                )
            )
            >= today
        )
    ]

    slate_dates = sorted(
        {
            valid_game_date(
                game.get(
                    "game_date"
                )
            )
            for game
            in future_games
        }
    )

    slate_dates = [
        slate_date
        for slate_date in slate_dates
        if slate_date is not None
    ]

    current_date = (
        slate_dates[0]
        if slate_dates
        else None
    )

    next_date = (
        slate_dates[1]
        if len(
            slate_dates
        ) > 1
        else None
    )

    current_games = [
        game
        for game in future_games
        if valid_game_date(
            game.get(
                "game_date"
            )
        ) == current_date
    ]

    next_games = [
        game
        for game in future_games
        if valid_game_date(
            game.get(
                "game_date"
            )
        ) == next_date
    ]

    current_payload = {
        "season": CURRENT_SEASON,
        "slate_date": (
            current_date.isoformat()
            if current_date
            else ""
        ),
        "game_count": len(
            current_games
        ),
        "games": current_games,
    }

    next_payload = {
        "season": CURRENT_SEASON,
        "slate_date": (
            next_date.isoformat()
            if next_date
            else ""
        ),
        "game_count": len(
            next_games
        ),
        "games": next_games,
    }

    write_output(
        "slate.json",
        current_payload,
    )

    MODEL_OUTPUT_DIR.joinpath(
        "next"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    WEB_OUTPUT_DIR.joinpath(
        "next"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(
        next_payload,
        MODEL_OUTPUT_DIR
        / "next"
        / "slate.json",
    )

    save_json(
        next_payload,
        WEB_OUTPUT_DIR
        / "next"
        / "slate.json",
    )

    print(
        "✅ next/slate.json"
    )


def build_all_nfl_data():
    print(
        "\n🏈 BUILDING NFL DATA\n"
    )

    build_teams()

    build_rosters()

    build_season_stats()

    build_career_stats()

    schedule = build_schedule()

    build_slates(
        schedule
    )

    print(
        "\n✅ NFL DATA BUILD COMPLETE\n"
    )


if __name__ == "__main__":
    build_all_nfl_data()