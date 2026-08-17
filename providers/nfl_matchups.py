from __future__ import annotations

from pathlib import Path
from typing import Any

import nflreadpy as nfl

from utils.json_utils import load_json, save_json


MODEL_ROOT = Path(__file__).resolve().parents[1]

NFL_DIR = (
    MODEL_ROOT
    / "data"
    / "processed"
    / "nfl"
)

WEB_NFL_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nfl"
)

ROSTERS_FILE = (
    NFL_DIR
    / "rosters.json"
)

SLATE_FILE = (
    NFL_DIR
    / "slate.json"
)

NEXT_SLATE_FILE = (
    NFL_DIR
    / "next"
    / "slate.json"
)

CURRENT_SEASON = 2026

HISTORY_START_SEASON = 2016

OFFENSIVE_POSITIONS = {
    "QB",
    "RB",
    "FB",
    "WR",
    "TE",
}


def f(
    value: Any,
    default=0.0,
):
    try:
        if value in (
            "",
            None,
        ):
            return default

        return float(value)

    except Exception:
        return default


def clean_text(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def normalize_team(
    value: Any,
) -> str:
    return clean_text(
        value
    ).upper()


def normalize_position(
    value: Any,
) -> str:
    return clean_text(
        value
    ).upper()


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


def polars_records(
    frame,
) -> list[dict[str, Any]]:
    if frame is None:
        return []

    try:
        rows = frame.to_dicts()
    except Exception:
        return []

    cleaned = []

    for row in rows:
        cleaned_row = {}

        for key, value in row.items():
            if hasattr(
                value,
                "item",
            ):
                try:
                    value = value.item()
                except Exception:
                    pass

            if hasattr(
                value,
                "isoformat",
            ):
                try:
                    value = value.isoformat()
                except Exception:
                    pass

            cleaned_row[
                key
            ] = value

        cleaned.append(
            cleaned_row
        )

    return cleaned


def load_history_rows():
    rows = []

    for season in range(
        HISTORY_START_SEASON,
        CURRENT_SEASON,
    ):
        try:
            print(
                f"   Loading {season}..."
            )

            frame = (
                nfl.load_player_stats(
                    [season]
                )
            )

            season_rows = (
                polars_records(
                    frame
                )
            )

            rows.extend(
                season_rows
            )

            print(
                f"   ✅ {season}: "
                f"{len(season_rows)} rows"
            )

        except Exception as exc:
            print(
                f"   ⚠️ {season}: "
                f"{exc}"
            )

    return rows


def roster_lookup(
    rosters: list[
        dict[str, Any]
    ],
):
    lookup: dict[
        str,
        list[
            dict[str, Any]
        ],
    ] = {}

    for player in rosters:
        team = normalize_team(
            player.get(
                "team"
            )
        )

        position = (
            normalize_position(
                player.get(
                    "position"
                )
            )
        )

        if (
            not team
            or position
            not in OFFENSIVE_POSITIONS
        ):
            continue

        lookup.setdefault(
            team,
            [],
        ).append(
            player
        )

    for team in lookup:
        lookup[
            team
        ].sort(
            key=lambda row: (
                row.get(
                    "position",
                    "",
                ),
                row.get(
                    "player",
                    "",
                ),
            )
        )

    return lookup


def historical_rows_by_player(
    rows: list[
        dict[str, Any]
    ],
):
    lookup: dict[
        str,
        list[
            dict[str, Any]
        ],
    ] = {}

    for row in rows:
        player_id = clean_text(
            get_first(
                row,
                "player_id",
                "gsis_id",
            )
        )

        if not player_id:
            continue

        lookup.setdefault(
            player_id,
            [],
        ).append(
            row
        )

    return lookup


def opponent_from_row(
    row: dict[str, Any],
):
    return normalize_team(
        get_first(
            row,
            "opponent_team",
            "opponent",
            "opp_team",
        )
    )


def build_player_vs_opponent(
    player: dict[str, Any],
    opponent: str,
    player_history: dict[
        str,
        list[
            dict[str, Any]
        ],
    ],
):
    player_id = clean_text(
        player.get(
            "player_id"
        )
    )

    history = (
        player_history.get(
            player_id,
            [],
        )
    )

    opponent = normalize_team(
        opponent
    )

    games = []

    for row in history:
        row_opponent = (
            opponent_from_row(
                row
            )
        )

        if (
            not row_opponent
            or row_opponent
            != opponent
        ):
            continue

        season_type = (
            clean_text(
                get_first(
                    row,
                    "season_type",
                    default="REG",
                )
            ).upper()
        )

        if season_type not in {
            "",
            "REG",
        }:
            continue

        games.append(
            row
        )

    game_count = len(
        games
    )

    base = {
        "player_id": (
            player.get(
                "player_id"
            )
        ),
        "player": (
            player.get(
                "player"
            )
        ),
        "team": (
            player.get(
                "team"
            )
        ),
        "position": (
            player.get(
                "position"
            )
        ),
        "opponent": opponent,
        "games_vs_opponent": (
            game_count
        ),
    }

    if not games:
        return {
            **base,

            "passing": {
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

            "averages": {
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

            "pass_yards_per_game": 0,
            "pass_tds_per_game": 0,
            "interceptions_per_game": 0,

            "carries_per_game": 0,
            "rush_yards_per_game": 0,
            "rush_tds_per_game": 0,

            "targets_per_game": 0,
            "receptions_per_game": 0,
            "receiving_yards_per_game": 0,
            "receiving_tds_per_game": 0,

            "fantasy_points_per_game": 0,
            "fantasy_points_ppr_per_game": 0,
        }

    # -----------------------------
    # TOTALS VS OPPONENT
    # -----------------------------
    totals = {
        "passing_yards": 0.0,
        "passing_tds": 0.0,
        "interceptions": 0.0,

        "carries": 0.0,
        "rushing_yards": 0.0,
        "rushing_tds": 0.0,

        "targets": 0.0,
        "receptions": 0.0,
        "receiving_yards": 0.0,
        "receiving_tds": 0.0,

        "fantasy_points": 0.0,
        "fantasy_points_ppr": 0.0,
    }

    for row in games:
        totals[
            "passing_yards"
        ] += f(
            get_first(
                row,
                "passing_yards",
                default=0,
            )
        )

        totals[
            "passing_tds"
        ] += f(
            get_first(
                row,
                "passing_tds",
                default=0,
            )
        )

        totals[
            "interceptions"
        ] += f(
            get_first(
                row,
                "interceptions",
                default=0,
            )
        )

        totals[
            "carries"
        ] += f(
            get_first(
                row,
                "carries",
                "rushing_attempts",
                default=0,
            )
        )

        totals[
            "rushing_yards"
        ] += f(
            get_first(
                row,
                "rushing_yards",
                default=0,
            )
        )

        totals[
            "rushing_tds"
        ] += f(
            get_first(
                row,
                "rushing_tds",
                default=0,
            )
        )

        totals[
            "targets"
        ] += f(
            get_first(
                row,
                "targets",
                default=0,
            )
        )

        totals[
            "receptions"
        ] += f(
            get_first(
                row,
                "receptions",
                default=0,
            )
        )

        totals[
            "receiving_yards"
        ] += f(
            get_first(
                row,
                "receiving_yards",
                default=0,
            )
        )

        totals[
            "receiving_tds"
        ] += f(
            get_first(
                row,
                "receiving_tds",
                default=0,
            )
        )

        totals[
            "fantasy_points"
        ] += f(
            get_first(
                row,
                "fantasy_points",
                default=0,
            )
        )

        totals[
            "fantasy_points_ppr"
        ] += f(
            get_first(
                row,
                "fantasy_points_ppr",
                default=0,
            )
        )

    divisor = max(
        1,
        game_count,
    )

    return {
        **base,

        # -----------------------------
        # CAREER TOTALS VS OPPONENT
        # -----------------------------
        "passing": {
            "yards": round(
                totals[
                    "passing_yards"
                ],
                1,
            ),
            "tds": round(
                totals[
                    "passing_tds"
                ],
                1,
            ),
            "interceptions": round(
                totals[
                    "interceptions"
                ],
                1,
            ),
        },

        "rushing": {
            "carries": round(
                totals[
                    "carries"
                ],
                1,
            ),
            "yards": round(
                totals[
                    "rushing_yards"
                ],
                1,
            ),
            "tds": round(
                totals[
                    "rushing_tds"
                ],
                1,
            ),
        },

        "receiving": {
            "targets": round(
                totals[
                    "targets"
                ],
                1,
            ),
            "receptions": round(
                totals[
                    "receptions"
                ],
                1,
            ),
            "yards": round(
                totals[
                    "receiving_yards"
                ],
                1,
            ),
            "tds": round(
                totals[
                    "receiving_tds"
                ],
                1,
            ),
        },

        "fantasy": {
            "points": round(
                totals[
                    "fantasy_points"
                ],
                1,
            ),
            "ppr_points": round(
                totals[
                    "fantasy_points_ppr"
                ],
                1,
            ),
        },

        # -----------------------------
        # PER-GAME AVERAGES VS OPPONENT
        # -----------------------------
        "averages": {
            "passing_yards": round(
                totals[
                    "passing_yards"
                ]
                / divisor,
                1,
            ),

            "passing_tds": round(
                totals[
                    "passing_tds"
                ]
                / divisor,
                2,
            ),

            "interceptions": round(
                totals[
                    "interceptions"
                ]
                / divisor,
                2,
            ),

            "carries": round(
                totals[
                    "carries"
                ]
                / divisor,
                1,
            ),

            "rushing_yards": round(
                totals[
                    "rushing_yards"
                ]
                / divisor,
                1,
            ),

            "rushing_tds": round(
                totals[
                    "rushing_tds"
                ]
                / divisor,
                2,
            ),

            "targets": round(
                totals[
                    "targets"
                ]
                / divisor,
                1,
            ),

            "receptions": round(
                totals[
                    "receptions"
                ]
                / divisor,
                1,
            ),

            "receiving_yards": round(
                totals[
                    "receiving_yards"
                ]
                / divisor,
                1,
            ),

            "receiving_tds": round(
                totals[
                    "receiving_tds"
                ]
                / divisor,
                2,
            ),

            "fantasy_points": round(
                totals[
                    "fantasy_points"
                ]
                / divisor,
                1,
            ),

            "fantasy_points_ppr": round(
                totals[
                    "fantasy_points_ppr"
                ]
                / divisor,
                1,
            ),
        },

        # -----------------------------
        # EXISTING SLATE-SUMMARY FIELDS
        # -----------------------------
        "pass_yards_per_game": round(
            totals[
                "passing_yards"
            ]
            / divisor,
            1,
        ),

        "pass_tds_per_game": round(
            totals[
                "passing_tds"
            ]
            / divisor,
            2,
        ),

        "interceptions_per_game": round(
            totals[
                "interceptions"
            ]
            / divisor,
            2,
        ),

        "carries_per_game": round(
            totals[
                "carries"
            ]
            / divisor,
            1,
        ),

        "rush_yards_per_game": round(
            totals[
                "rushing_yards"
            ]
            / divisor,
            1,
        ),

        "rush_tds_per_game": round(
            totals[
                "rushing_tds"
            ]
            / divisor,
            2,
        ),

        "targets_per_game": round(
            totals[
                "targets"
            ]
            / divisor,
            1,
        ),

        "receptions_per_game": round(
            totals[
                "receptions"
            ]
            / divisor,
            1,
        ),

        "receiving_yards_per_game": round(
            totals[
                "receiving_yards"
            ]
            / divisor,
            1,
        ),

        "receiving_tds_per_game": round(
            totals[
                "receiving_tds"
            ]
            / divisor,
            2,
        ),

        "fantasy_points_per_game": round(
            totals[
                "fantasy_points"
            ]
            / divisor,
            1,
        ),

        "fantasy_points_ppr_per_game": round(
            totals[
                "fantasy_points_ppr"
            ]
            / divisor,
            1,
        ),
    }


def attach_players_to_slate(
    slate_file: Path,
    output_file: Path,
    web_output_file: Path,
    rosters_by_team,
    player_history,
):
    payload = load_json(
        slate_file,
        default={},
    )

    games = payload.get(
        "games",
        [],
    )

    for game in games:
        away_team = (
            normalize_team(
                game.get(
                    "away_team"
                )
            )
        )

        home_team = (
            normalize_team(
                game.get(
                    "home_team"
                )
            )
        )

        away_players = []

        for player in rosters_by_team.get(
            away_team,
            [],
        ):
            away_players.append(
                build_player_vs_opponent(
                    player,
                    home_team,
                    player_history,
                )
            )

        home_players = []

        for player in rosters_by_team.get(
            home_team,
            [],
        ):
            home_players.append(
                build_player_vs_opponent(
                    player,
                    away_team,
                    player_history,
                )
            )

        game[
            "players"
        ] = {
            "away": (
                away_players
            ),
            "home": (
                home_players
            ),
        }

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    web_output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(
        payload,
        output_file,
    )

    save_json(
        payload,
        web_output_file,
    )

    print(
        f"✅ Updated "
        f"{output_file}"
    )


def build_nfl_matchups():
    print(
        "\n🏈 BUILDING NFL "
        "OPPONENT HISTORY\n"
    )

    rosters = load_json(
        ROSTERS_FILE,
        default=[],
    )

    print(
        f"   Rosters loaded: "
        f"{len(rosters)}"
    )

    rosters_by_team = (
        roster_lookup(
            rosters
        )
    )

    print(
        "   Loading historical "
        "player game data..."
    )

    rows = (
        load_history_rows()
    )

    print(
        f"   Historical rows: "
        f"{len(rows)}"
    )

    player_history = (
        historical_rows_by_player(
            rows
        )
    )

    attach_players_to_slate(
        SLATE_FILE,
        SLATE_FILE,
        WEB_NFL_DIR
        / "slate.json",
        rosters_by_team,
        player_history,
    )

    if NEXT_SLATE_FILE.exists():
        attach_players_to_slate(
            NEXT_SLATE_FILE,
            NEXT_SLATE_FILE,
            WEB_NFL_DIR
            / "next"
            / "slate.json",
            rosters_by_team,
            player_history,
        )

    print(
        "\n✅ NFL OPPONENT "
        "HISTORY COMPLETE\n"
    )


if __name__ == "__main__":
    build_nfl_matchups()