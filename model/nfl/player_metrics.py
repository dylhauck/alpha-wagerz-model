from __future__ import annotations

from pathlib import Path
from typing import Any

from utils.json_utils import load_json, save_json


MODEL_ROOT = Path(__file__).resolve().parents[2]

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

PLAYER_STATS_FILE = (
    NFL_DIR
    / "player_stats.json"
)

CAREER_STATS_FILE = (
    NFL_DIR
    / "career_stats.json"
)

ROSTERS_FILE = (
    NFL_DIR
    / "rosters.json"
)

OUTPUT_FILE = (
    NFL_DIR
    / "player_metrics.json"
)

WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "player_metrics.json"
)


# =========================================================
# SETTINGS
# =========================================================

CURRENT_SEASON = 2026
BASELINE_SEASON = 2025

SUPPORTED_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
}

MIN_GAMES_FOR_STABLE_RATE = 4


# =========================================================
# HELPERS
# =========================================================

def f(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value in (
            None,
            "",
        ):
            return default

        return float(value)

    except Exception:
        return default


def i(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value in (
            None,
            "",
        ):
            return default

        return int(
            float(value)
        )

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
    team = clean_text(
        value
    ).upper()

    aliases = {
        "LA": "LAR",
        "JAC": "JAX",
        "WSH": "WAS",
        "OAK": "LV",
        "SD": "LAC",
        "STL": "LAR",
    }

    return aliases.get(
        team,
        team,
    )


def normalize_position(
    value: Any,
) -> str:
    position = clean_text(
        value
    ).upper()

    aliases = {
        "HB": "RB",
        "FB": "RB",
    }

    return aliases.get(
        position,
        position,
    )


def safe_divide(
    numerator: Any,
    denominator: Any,
    digits: int = 3,
) -> float:
    denominator_value = f(
        denominator
    )

    if not denominator_value:
        return 0.0

    return round(
        f(numerator)
        / denominator_value,
        digits,
    )


def per_game(
    value: Any,
    games: Any,
    digits: int = 2,
) -> float:
    return safe_divide(
        value,
        games,
        digits,
    )


def percentage(
    numerator: Any,
    denominator: Any,
    digits: int = 1,
) -> float:
    denominator_value = f(
        denominator
    )

    if not denominator_value:
        return 0.0

    return round(
        (
            f(numerator)
            / denominator_value
        )
        * 100,
        digits,
    )


def first_value(
    payload: dict[str, Any],
    *keys: str,
    default=None,
):
    for key in keys:
        value = payload.get(
            key
        )

        if value not in (
            None,
            "",
        ):
            return value

    return default


# =========================================================
# LOADERS
# =========================================================

def list_payload(
    payload: Any,
    *possible_keys: str,
):
    if isinstance(
        payload,
        list,
    ):
        return payload

    if isinstance(
        payload,
        dict,
    ):
        for key in possible_keys:
            value = payload.get(
                key
            )

            if isinstance(
                value,
                list,
            ):
                return value

    return []


def load_player_stats():
    payload = load_json(
        PLAYER_STATS_FILE,
        default=[],
    )

    return list_payload(
        payload,
        "players",
        "player_stats",
        "stats",
    )


def load_career_stats():
    payload = load_json(
        CAREER_STATS_FILE,
        default=[],
    )

    return list_payload(
        payload,
        "players",
        "career_stats",
        "stats",
    )


def load_rosters():
    payload = load_json(
        ROSTERS_FILE,
        default=[],
    )

    return list_payload(
        payload,
        "players",
        "rosters",
        "roster",
    )


# =========================================================
# ROSTER LOOKUP
# =========================================================

def build_roster_lookup(
    rows: list[
        dict[str, Any]
    ],
):
    lookup = {}

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        player_id = clean_text(
            first_value(
                row,
                "player_id",
                "gsis_id",
                "id",
            )
        )

        if not player_id:
            continue

        lookup[
            player_id
        ] = {
            "team": normalize_team(
                first_value(
                    row,
                    "team",
                    "team_abbr",
                    "recent_team",
                )
            ),

            "position": normalize_position(
                first_value(
                    row,
                    "position",
                    "pos",
                )
            ),

            "player": clean_text(
                first_value(
                    row,
                    "player",
                    "player_name",
                    "full_name",
                    "name",
                )
            ),
        }

    return lookup


# =========================================================
# CAREER LOOKUP
# =========================================================

def build_career_lookup(
    rows: list[
        dict[str, Any]
    ],
):
    lookup = {}

    for row in rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        player_id = clean_text(
            first_value(
                row,
                "player_id",
                "gsis_id",
                "id",
            )
        )

        if player_id:
            lookup[
                player_id
            ] = row

    return lookup


# =========================================================
# STAT EXTRACTION
# =========================================================

def extract_passing(
    row: dict[str, Any],
):
    passing = (
        row.get(
            "passing",
            {}
        )
        if isinstance(
            row.get(
                "passing"
            ),
            dict,
        )
        else {}
    )

    completions = f(
        first_value(
            passing,
            "completions",
            default=first_value(
                row,
                "completions",
                "passing_completions",
                default=0,
            ),
        )
    )

    attempts = f(
        first_value(
            passing,
            "attempts",
            default=first_value(
                row,
                "attempts",
                "passing_attempts",
                default=0,
            ),
        )
    )

    yards = f(
        first_value(
            passing,
            "yards",
            "passing_yards",
            default=first_value(
                row,
                "passing_yards",
                default=0,
            ),
        )
    )

    touchdowns = f(
        first_value(
            passing,
            "touchdowns",
            "tds",
            default=first_value(
                row,
                "passing_tds",
                "passing_touchdowns",
                default=0,
            ),
        )
    )

    interceptions = f(
        first_value(
            passing,
            "interceptions",
            "ints",
            default=first_value(
                row,
                "interceptions",
                default=0,
            ),
        )
    )

    return {
        "completions": completions,
        "attempts": attempts,
        "yards": yards,
        "touchdowns": touchdowns,
        "interceptions": interceptions,
    }


def extract_rushing(
    row: dict[str, Any],
):
    rushing = (
        row.get(
            "rushing",
            {}
        )
        if isinstance(
            row.get(
                "rushing"
            ),
            dict,
        )
        else {}
    )

    carries = f(
        first_value(
            rushing,
            "carries",
            "attempts",
            default=first_value(
                row,
                "carries",
                "rushing_attempts",
                default=0,
            ),
        )
    )

    yards = f(
        first_value(
            rushing,
            "yards",
            "rushing_yards",
            default=first_value(
                row,
                "rushing_yards",
                default=0,
            ),
        )
    )

    touchdowns = f(
        first_value(
            rushing,
            "touchdowns",
            "tds",
            default=first_value(
                row,
                "rushing_tds",
                "rushing_touchdowns",
                default=0,
            ),
        )
    )

    return {
        "carries": carries,
        "yards": yards,
        "touchdowns": touchdowns,
    }


def extract_receiving(
    row: dict[str, Any],
):
    receiving = (
        row.get(
            "receiving",
            {}
        )
        if isinstance(
            row.get(
                "receiving"
            ),
            dict,
        )
        else {}
    )

    targets = f(
        first_value(
            receiving,
            "targets",
            default=first_value(
                row,
                "targets",
                default=0,
            ),
        )
    )

    receptions = f(
        first_value(
            receiving,
            "receptions",
            default=first_value(
                row,
                "receptions",
                default=0,
            ),
        )
    )

    yards = f(
        first_value(
            receiving,
            "yards",
            "receiving_yards",
            default=first_value(
                row,
                "receiving_yards",
                default=0,
            ),
        )
    )

    touchdowns = f(
        first_value(
            receiving,
            "touchdowns",
            "tds",
            default=first_value(
                row,
                "receiving_tds",
                "receiving_touchdowns",
                default=0,
            ),
        )
    )

    return {
        "targets": targets,
        "receptions": receptions,
        "yards": yards,
        "touchdowns": touchdowns,
    }


def extract_fantasy(
    row: dict[str, Any],
):
    fantasy = (
        row.get(
            "fantasy",
            {}
        )
        if isinstance(
            row.get(
                "fantasy"
            ),
            dict,
        )
        else {}
    )

    standard = f(
        first_value(
            fantasy,
            "points",
            "fantasy_points",
            default=first_value(
                row,
                "fantasy_points",
                default=0,
            ),
        )
    )

    ppr = f(
        first_value(
            fantasy,
            "ppr_points",
            "fantasy_points_ppr",
            default=first_value(
                row,
                "fantasy_points_ppr",
                default=0,
            ),
        )
    )

    return {
        "points": standard,
        "ppr_points": ppr,
    }


# =========================================================
# PLAYER METRICS
# =========================================================

def build_player_metric(
    row: dict[str, Any],
    roster_lookup: dict[
        str,
        dict[str, Any]
    ],
    career_lookup: dict[
        str,
        dict[str, Any]
    ],
):
    player_id = clean_text(
        first_value(
            row,
            "player_id",
            "gsis_id",
            "id",
        )
    )

    roster = (
        roster_lookup.get(
            player_id,
            {},
        )
    )

    career = (
        career_lookup.get(
            player_id,
            {},
        )
    )

    player = clean_text(
        first_value(
            row,
            "player",
            "player_name",
            "name",
            default=roster.get(
                "player",
                "",
            ),
        )
    )

    team = normalize_team(
        first_value(
            row,
            "team",
            "recent_team",
            "team_abbr",
            default=roster.get(
                "team",
                "",
            ),
        )
    )

    position = normalize_position(
        first_value(
            row,
            "position",
            "pos",
            default=roster.get(
                "position",
                "",
            ),
        )
    )

    games = i(
        first_value(
            row,
            "games",
            "games_played",
            default=0,
        )
    )

    passing = extract_passing(
        row
    )

    rushing = extract_rushing(
        row
    )

    receiving = extract_receiving(
        row
    )

    fantasy = extract_fantasy(
        row
    )

    # -----------------------------------------------------
    # PASSING
    # -----------------------------------------------------

    completion_rate = percentage(
        passing[
            "completions"
        ],
        passing[
            "attempts"
        ],
    )

    yards_per_attempt = safe_divide(
        passing[
            "yards"
        ],
        passing[
            "attempts"
        ],
        2,
    )

    pass_td_rate = percentage(
        passing[
            "touchdowns"
        ],
        passing[
            "attempts"
        ],
    )

    interception_rate = percentage(
        passing[
            "interceptions"
        ],
        passing[
            "attempts"
        ],
    )

    # -----------------------------------------------------
    # RUSHING
    # -----------------------------------------------------

    yards_per_carry = safe_divide(
        rushing[
            "yards"
        ],
        rushing[
            "carries"
        ],
        2,
    )

    rush_td_rate = percentage(
        rushing[
            "touchdowns"
        ],
        rushing[
            "carries"
        ],
    )

    # -----------------------------------------------------
    # RECEIVING
    # -----------------------------------------------------

    catch_rate = percentage(
        receiving[
            "receptions"
        ],
        receiving[
            "targets"
        ],
    )

    yards_per_target = safe_divide(
        receiving[
            "yards"
        ],
        receiving[
            "targets"
        ],
        2,
    )

    yards_per_reception = safe_divide(
        receiving[
            "yards"
        ],
        receiving[
            "receptions"
        ],
        2,
    )

    receiving_td_rate = percentage(
        receiving[
            "touchdowns"
        ],
        receiving[
            "targets"
        ],
    )

    # -----------------------------------------------------
    # OPPORTUNITY / USAGE
    # -----------------------------------------------------

    opportunities = (
        rushing[
            "carries"
        ]
        + receiving[
            "targets"
        ]
    )

    touches = (
        rushing[
            "carries"
        ]
        + receiving[
            "receptions"
        ]
    )

    opportunities_per_game = per_game(
        opportunities,
        games,
    )

    touches_per_game = per_game(
        touches,
        games,
    )

    # -----------------------------------------------------
    # CAREER CONTEXT
    # -----------------------------------------------------

    career_totals = (
        career.get(
            "career_totals",
            {},
        )
        if isinstance(
            career.get(
                "career_totals"
            ),
            dict,
        )
        else {}
    )

    career_averages = (
        career.get(
            "career_averages",
            {},
        )
        if isinstance(
            career.get(
                "career_averages"
            ),
            dict,
        )
        else {}
    )

    career_games = i(
        career_totals.get(
            "games"
        )
    )

    # -----------------------------------------------------
    # RELIABILITY
    # -----------------------------------------------------

    if games >= 12:
        sample_label = (
            "Strong"
        )

    elif games >= 8:
        sample_label = (
            "Good"
        )

    elif games >= (
        MIN_GAMES_FOR_STABLE_RATE
    ):
        sample_label = (
            "Moderate"
        )

    elif games > 0:
        sample_label = (
            "Small"
        )

    else:
        sample_label = (
            "No Sample"
        )

    return {
        "player_id": (
            player_id
        ),

        "player": (
            player
        ),

        "team": (
            team
        ),

        "position": (
            position
        ),

        "season": (
            BASELINE_SEASON
        ),

        "games": (
            games
        ),

        "sample": {
            "games": (
                games
            ),

            "label": (
                sample_label
            ),
        },

        "passing": {
            "completions": round(
                passing[
                    "completions"
                ],
                1,
            ),

            "attempts": round(
                passing[
                    "attempts"
                ],
                1,
            ),

            "yards": round(
                passing[
                    "yards"
                ],
                1,
            ),

            "touchdowns": round(
                passing[
                    "touchdowns"
                ],
                1,
            ),

            "interceptions": round(
                passing[
                    "interceptions"
                ],
                1,
            ),

            "attempts_per_game": (
                per_game(
                    passing[
                        "attempts"
                    ],
                    games,
                )
            ),

            "completions_per_game": (
                per_game(
                    passing[
                        "completions"
                    ],
                    games,
                )
            ),

            "yards_per_game": (
                per_game(
                    passing[
                        "yards"
                    ],
                    games,
                )
            ),

            "touchdowns_per_game": (
                per_game(
                    passing[
                        "touchdowns"
                    ],
                    games,
                )
            ),

            "interceptions_per_game": (
                per_game(
                    passing[
                        "interceptions"
                    ],
                    games,
                )
            ),

            "completion_rate": (
                completion_rate
            ),

            "yards_per_attempt": (
                yards_per_attempt
            ),

            "touchdown_rate": (
                pass_td_rate
            ),

            "interception_rate": (
                interception_rate
            ),
        },

        "rushing": {
            "carries": round(
                rushing[
                    "carries"
                ],
                1,
            ),

            "yards": round(
                rushing[
                    "yards"
                ],
                1,
            ),

            "touchdowns": round(
                rushing[
                    "touchdowns"
                ],
                1,
            ),

            "carries_per_game": (
                per_game(
                    rushing[
                        "carries"
                    ],
                    games,
                )
            ),

            "yards_per_game": (
                per_game(
                    rushing[
                        "yards"
                    ],
                    games,
                )
            ),

            "touchdowns_per_game": (
                per_game(
                    rushing[
                        "touchdowns"
                    ],
                    games,
                )
            ),

            "yards_per_carry": (
                yards_per_carry
            ),

            "touchdown_rate": (
                rush_td_rate
            ),
        },

        "receiving": {
            "targets": round(
                receiving[
                    "targets"
                ],
                1,
            ),

            "receptions": round(
                receiving[
                    "receptions"
                ],
                1,
            ),

            "yards": round(
                receiving[
                    "yards"
                ],
                1,
            ),

            "touchdowns": round(
                receiving[
                    "touchdowns"
                ],
                1,
            ),

            "targets_per_game": (
                per_game(
                    receiving[
                        "targets"
                    ],
                    games,
                )
            ),

            "receptions_per_game": (
                per_game(
                    receiving[
                        "receptions"
                    ],
                    games,
                )
            ),

            "yards_per_game": (
                per_game(
                    receiving[
                        "yards"
                    ],
                    games,
                )
            ),

            "touchdowns_per_game": (
                per_game(
                    receiving[
                        "touchdowns"
                    ],
                    games,
                )
            ),

            "catch_rate": (
                catch_rate
            ),

            "yards_per_target": (
                yards_per_target
            ),

            "yards_per_reception": (
                yards_per_reception
            ),

            "touchdown_rate": (
                receiving_td_rate
            ),
        },

        "usage": {
            "opportunities": round(
                opportunities,
                1,
            ),

            "opportunities_per_game": (
                opportunities_per_game
            ),

            "touches": round(
                touches,
                1,
            ),

            "touches_per_game": (
                touches_per_game
            ),
        },

        "fantasy": {
            "points": round(
                fantasy[
                    "points"
                ],
                2,
            ),

            "ppr_points": round(
                fantasy[
                    "ppr_points"
                ],
                2,
            ),

            "points_per_game": (
                per_game(
                    fantasy[
                        "points"
                    ],
                    games,
                )
            ),

            "ppr_points_per_game": (
                per_game(
                    fantasy[
                        "ppr_points"
                    ],
                    games,
                )
            ),
        },

        "career": {
            "games": (
                career_games
            ),

            "totals": (
                career_totals
            ),

            "averages": (
                career_averages
            ),
        },
    }


# =========================================================
# BUILD
# =========================================================

def build_nfl_player_metrics():
    print(
        "\n🏈 BUILDING NFL "
        "PLAYER METRICS\n"
    )

    player_rows = (
        load_player_stats()
    )

    career_rows = (
        load_career_stats()
    )

    roster_rows = (
        load_rosters()
    )

    print(
        f"   Player stats: "
        f"{len(player_rows)}"
    )

    print(
        f"   Career profiles: "
        f"{len(career_rows)}"
    )

    print(
        f"   Roster players: "
        f"{len(roster_rows)}"
    )

    roster_lookup = (
        build_roster_lookup(
            roster_rows
        )
    )

    career_lookup = (
        build_career_lookup(
            career_rows
        )
    )

    players = []

    skipped_position = 0
    skipped_id = 0

    for row in player_rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        metric = (
            build_player_metric(
                row,
                roster_lookup,
                career_lookup,
            )
        )

        if not metric[
            "player_id"
        ]:
            skipped_id += 1
            continue

        if (
            metric[
                "position"
            ]
            not in SUPPORTED_POSITIONS
        ):
            skipped_position += 1
            continue

        players.append(
            metric
        )

    position_counts = {
        "QB": 0,
        "RB": 0,
        "WR": 0,
        "TE": 0,
    }

    for player in players:
        position = player.get(
            "position"
        )

        if position in (
            position_counts
        ):
            position_counts[
                position
            ] += 1

    players.sort(
        key=lambda player: (
            player.get(
                "team",
                "",
            ),
            player.get(
                "position",
                "",
            ),
            player.get(
                "player",
                "",
            ),
        )
    )

    payload = {
        "season": (
            BASELINE_SEASON
        ),

        "model_season": (
            CURRENT_SEASON
        ),

        "players": (
            players
        ),

        "counts": {
            "total": (
                len(players)
            ),

            "QB": (
                position_counts[
                    "QB"
                ]
            ),

            "RB": (
                position_counts[
                    "RB"
                ]
            ),

            "WR": (
                position_counts[
                    "WR"
                ]
            ),

            "TE": (
                position_counts[
                    "TE"
                ]
            ),

            "skipped_position": (
                skipped_position
            ),

            "skipped_id": (
                skipped_id
            ),
        },
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    WEB_OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(
        payload,
        OUTPUT_FILE,
    )

    save_json(
        payload,
        WEB_OUTPUT_FILE,
    )

    print(
        f"\n   Eligible players: "
        f"{len(players)}"
    )

    print(
        f"   QB: "
        f"{position_counts['QB']}"
    )

    print(
        f"   RB: "
        f"{position_counts['RB']}"
    )

    print(
        f"   WR: "
        f"{position_counts['WR']}"
    )

    print(
        f"   TE: "
        f"{position_counts['TE']}"
    )

    print(
        f"\n   model: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"   web:   "
        f"{WEB_OUTPUT_FILE}"
    )

    print(
        "\n✅ NFL PLAYER METRICS "
        "COMPLETE\n"
    )

    return payload


if __name__ == "__main__":
    build_nfl_player_metrics()
