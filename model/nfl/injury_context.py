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

INJURY_FILE = (
    NFL_DIR
    / "injuries.json"
)

ROSTERS_FILE = (
    NFL_DIR
    / "rosters.json"
)

PLAYER_METRICS_FILE = (
    NFL_DIR
    / "player_metrics.json"
)

SLATE_FILE = (
    NFL_DIR
    / "slate.json"
)

OUTPUT_FILE = (
    NFL_DIR
    / "injury_context.json"
)

WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "injury_context.json"
)

NEXT_SLATE_FILE = (
    NFL_DIR
    / "next"
    / "slate.json"
)

NEXT_OUTPUT_FILE = (
    NFL_DIR
    / "next"
    / "injury_context.json"
)

NEXT_WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "next"
    / "injury_context.json"
)


# =========================================================
# SETTINGS
# =========================================================

OFFENSIVE_POSITIONS = {
    "QB",
    "RB",
    "WR",
    "TE",
    "OT",
    "LT",
    "RT",
    "OG",
    "LG",
    "RG",
    "C",
    "OL",
}

DEFENSIVE_POSITIONS = {
    "DE",
    "DT",
    "DL",
    "NT",
    "EDGE",
    "LB",
    "ILB",
    "OLB",
    "CB",
    "DB",
    "S",
    "FS",
    "SS",
}

POSITION_WEIGHTS = {
    # Offense
    "QB": 10.0,

    "LT": 4.0,
    "RT": 3.2,
    "OT": 3.2,

    "LG": 2.0,
    "RG": 2.0,
    "OG": 2.0,
    "C": 2.4,
    "OL": 2.0,

    "WR": 3.0,
    "TE": 2.2,
    "RB": 1.8,

    # Defense
    "EDGE": 4.0,
    "DE": 3.5,

    "DT": 2.6,
    "NT": 2.4,
    "DL": 2.5,

    "CB": 3.4,

    "S": 2.5,
    "FS": 2.5,
    "SS": 2.5,
    "DB": 2.4,

    "LB": 2.4,
    "ILB": 2.4,
    "OLB": 2.7,
}

STATUS_WEIGHTS = {
    "OUT": 1.00,
    "IR": 1.00,
    "INJURED RESERVE": 1.00,
    "PUP": 1.00,
    "NFI": 1.00,

    "DOUBTFUL": 0.85,

    "QUESTIONABLE": 0.40,

    "LIMITED": 0.20,

    "PROBABLE": 0.08,

    "ACTIVE": 0.00,
    "FULL": 0.00,
}

MAX_OFFENSIVE_PENALTY = 18.0
MAX_DEFENSIVE_PENALTY = 18.0

MAX_PASS_PENALTY = 20.0
MAX_RUSH_PENALTY = 16.0

MAX_PLAYER_OPPORTUNITY_BOOST = 1.30


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

        "T": "OT",
        "G": "OG",

        "CORNERBACK": "CB",
        "SAFETY": "S",

        "DEFENSIVE END": "DE",
        "DEFENSIVE TACKLE": "DT",
        "LINEBACKER": "LB",
    }

    return aliases.get(
        position,
        position,
    )


def normalize_status(
    value: Any,
) -> str:
    status = clean_text(
        value
    ).upper()

    aliases = {
        "Q": "QUESTIONABLE",
        "QUES": "QUESTIONABLE",

        "D": "DOUBTFUL",

        "O": "OUT",

        "IR-R": "IR",
        "RESERVE/INJURED": "IR",

        "PUP-R": "PUP",

        "LP": "LIMITED",
        "LIMITED PARTICIPATION": "LIMITED",

        "FP": "FULL",
        "FULL PARTICIPATION": "FULL",
    }

    return aliases.get(
        status,
        status,
    )


def clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(
            maximum,
            value,
        ),
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


def extract_list(
    payload: Any,
    *keys: str,
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
        for key in keys:
            value = payload.get(
                key
            )

            if isinstance(
                value,
                list,
            ):
                return value

    return []


# =========================================================
# PLAYER LOOKUPS
# =========================================================

def build_player_metric_lookup(
    payload: Any,
):
    rows = extract_list(
        payload,
        "players",
        "player_metrics",
    )

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


def build_roster_lookup(
    payload: Any,
):
    rows = extract_list(
        payload,
        "players",
        "rosters",
        "roster",
    )

    by_id = {}
    by_name = {}

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

        player = clean_text(
            first_value(
                row,
                "player",
                "player_name",
                "full_name",
                "name",
            )
        )

        team = normalize_team(
            first_value(
                row,
                "team",
                "team_abbr",
                "recent_team",
            )
        )

        position = normalize_position(
            first_value(
                row,
                "position",
                "pos",
            )
        )

        normalized = {
            "player_id": player_id,
            "player": player,
            "team": team,
            "position": position,
        }

        if player_id:
            by_id[
                player_id
            ] = normalized

        if player:
            by_name[
                player.lower()
            ] = normalized

    return (
        by_id,
        by_name,
    )


# =========================================================
# PLAYER IMPORTANCE
# =========================================================

def usage_importance(
    player_metrics: dict[str, Any],
    position: str,
):
    if not player_metrics:
        return 1.0

    if position == "QB":
        attempts = f(
            player_metrics.get(
                "passing",
                {},
            ).get(
                "attempts_per_game"
            )
        )

        if attempts >= 30:
            return 1.30

        if attempts >= 20:
            return 1.15

        return 1.0

    if position == "RB":
        opportunities = f(
            player_metrics.get(
                "usage",
                {},
            ).get(
                "opportunities_per_game"
            )
        )

        if opportunities >= 18:
            return 1.30

        if opportunities >= 12:
            return 1.15

        if opportunities >= 7:
            return 1.05

        return 0.85

    if position in {
        "WR",
        "TE",
    }:
        targets = f(
            player_metrics.get(
                "receiving",
                {},
            ).get(
                "targets_per_game"
            )
        )

        if targets >= 9:
            return 1.30

        if targets >= 7:
            return 1.20

        if targets >= 5:
            return 1.10

        if targets >= 3:
            return 0.95

        return 0.80

    return 1.0


# =========================================================
# NORMALIZE INJURY
# =========================================================

def normalize_injury(
    row: dict[str, Any],
    roster_by_id: dict[str, Any],
    roster_by_name: dict[str, Any],
    player_metrics: dict[str, Any],
):
    player_id = clean_text(
        first_value(
            row,
            "player_id",
            "gsis_id",
            "id",
            "athlete_id",
        )
    )

    player = clean_text(
        first_value(
            row,
            "player",
            "player_name",
            "name",
            "athlete",
        )
    )

    roster = {}

    if player_id:
        roster = (
            roster_by_id.get(
                player_id,
                {},
            )
        )

    if (
        not roster
        and player
    ):
        roster = (
            roster_by_name.get(
                player.lower(),
                {},
            )
        )

    if not player_id:
        player_id = clean_text(
            roster.get(
                "player_id"
            )
        )

    if not player:
        player = clean_text(
            roster.get(
                "player"
            )
        )

    team = normalize_team(
        first_value(
            row,
            "team",
            "team_abbr",
            "recent_team",
            default=roster.get(
                "team"
            ),
        )
    )

    position = normalize_position(
        first_value(
            row,
            "position",
            "pos",
            default=roster.get(
                "position"
            ),
        )
    )

    status = normalize_status(
        first_value(
            row,
            "status",
            "injury_status",
            "designation",
            "game_status",
        )
    )

    injury = clean_text(
        first_value(
            row,
            "injury",
            "body_part",
            "description",
            "detail",
        )
    )

    practice_status = normalize_status(
        first_value(
            row,
            "practice_status",
            "practice",
        )
    )

    status_weight = STATUS_WEIGHTS.get(
        status,
        0.0,
    )

    if (
        status_weight == 0
        and practice_status
    ):
        status_weight = (
            STATUS_WEIGHTS.get(
                practice_status,
                0.0,
            )
        )

    metrics = (
        player_metrics.get(
            player_id,
            {},
        )
        if player_id
        else {}
    )

    importance = usage_importance(
        metrics,
        position,
    )

    base_position_weight = (
        POSITION_WEIGHTS.get(
            position,
            1.0,
        )
    )

    impact = (
        base_position_weight
        * status_weight
        * importance
    )

    if position in (
        OFFENSIVE_POSITIONS
    ):
        unit = "offense"

    elif position in (
        DEFENSIVE_POSITIONS
    ):
        unit = "defense"

    else:
        unit = "other"

    return {
        "player_id": player_id,
        "player": player,
        "team": team,
        "position": position,

        "status": status,

        "practice_status": (
            practice_status
        ),

        "injury": injury,

        "unit": unit,

        "position_weight": round(
            base_position_weight,
            2,
        ),

        "status_weight": round(
            status_weight,
            2,
        ),

        "usage_importance": round(
            importance,
            2,
        ),

        "impact": round(
            impact,
            2,
        ),
    }


# =========================================================
# TEAM CONTEXT
# =========================================================

def empty_team_context(
    team: str,
):
    return {
        "team": team,

        "injuries": [],

        "offense": {
            "impact": 0.0,
            "factor": 1.0,

            "passing_impact": 0.0,
            "passing_factor": 1.0,

            "rushing_impact": 0.0,
            "rushing_factor": 1.0,
        },

        "defense": {
            "impact": 0.0,
            "factor": 1.0,

            "pass_defense_impact": 0.0,
            "pass_defense_factor": 1.0,

            "rush_defense_impact": 0.0,
            "rush_defense_factor": 1.0,
        },

        "key_absences": [],
    }


def add_injury_to_team(
    context: dict[str, Any],
    injury: dict[str, Any],
):
    context[
        "injuries"
    ].append(
        injury
    )

    impact = f(
        injury.get(
            "impact"
        )
    )

    position = injury.get(
        "position"
    )

    unit = injury.get(
        "unit"
    )

    if unit == "offense":
        context[
            "offense"
        ][
            "impact"
        ] += impact

        if position in {
            "QB",
            "WR",
            "TE",
            "LT",
            "RT",
            "OT",
            "LG",
            "RG",
            "OG",
            "C",
            "OL",
        }:
            context[
                "offense"
            ][
                "passing_impact"
            ] += impact

        if position in {
            "QB",
            "RB",
            "LT",
            "RT",
            "OT",
            "LG",
            "RG",
            "OG",
            "C",
            "OL",
        }:
            context[
                "offense"
            ][
                "rushing_impact"
            ] += impact

    elif unit == "defense":
        context[
            "defense"
        ][
            "impact"
        ] += impact

        if position in {
            "EDGE",
            "DE",
            "CB",
            "DB",
            "S",
            "FS",
            "SS",
            "LB",
            "ILB",
            "OLB",
        }:
            context[
                "defense"
            ][
                "pass_defense_impact"
            ] += impact

        if position in {
            "DT",
            "NT",
            "DL",
            "DE",
            "EDGE",
            "LB",
            "ILB",
            "OLB",
            "S",
            "SS",
            "FS",
        }:
            context[
                "defense"
            ][
                "rush_defense_impact"
            ] += impact

    if impact >= 2.5:
        context[
            "key_absences"
        ].append(
            {
                "player_id": injury.get(
                    "player_id"
                ),

                "player": injury.get(
                    "player"
                ),

                "position": position,

                "status": injury.get(
                    "status"
                ),

                "injury": injury.get(
                    "injury"
                ),

                "impact": round(
                    impact,
                    2,
                ),
            }
        )


# =========================================================
# FINALIZE TEAM
# =========================================================

def finalize_team_context(
    context: dict[str, Any],
):
    offense = context[
        "offense"
    ]

    defense = context[
        "defense"
    ]

    offense_impact = clamp(
        f(
            offense[
                "impact"
            ]
        ),
        0,
        MAX_OFFENSIVE_PENALTY,
    )

    passing_impact = clamp(
        f(
            offense[
                "passing_impact"
            ]
        ),
        0,
        MAX_PASS_PENALTY,
    )

    rushing_impact = clamp(
        f(
            offense[
                "rushing_impact"
            ]
        ),
        0,
        MAX_RUSH_PENALTY,
    )

    defense_impact = clamp(
        f(
            defense[
                "impact"
            ]
        ),
        0,
        MAX_DEFENSIVE_PENALTY,
    )

    pass_defense_impact = clamp(
        f(
            defense[
                "pass_defense_impact"
            ]
        ),
        0,
        MAX_PASS_PENALTY,
    )

    rush_defense_impact = clamp(
        f(
            defense[
                "rush_defense_impact"
            ]
        ),
        0,
        MAX_RUSH_PENALTY,
    )

    # Offense:
    # lower factor = weaker offense due
    # to unavailable players.

    offense_factor = clamp(
        1.0
        - offense_impact * 0.012,
        0.80,
        1.0,
    )

    passing_factor = clamp(
        1.0
        - passing_impact * 0.013,
        0.78,
        1.0,
    )

    rushing_factor = clamp(
        1.0
        - rushing_impact * 0.011,
        0.82,
        1.0,
    )

    # Defense:
    # factor > 1 means the opponent gets
    # a positive offensive adjustment
    # because this defense is weakened.

    defense_factor = clamp(
        1.0
        + defense_impact * 0.010,
        1.0,
        1.18,
    )

    pass_defense_factor = clamp(
        1.0
        + pass_defense_impact * 0.011,
        1.0,
        1.20,
    )

    rush_defense_factor = clamp(
        1.0
        + rush_defense_impact * 0.010,
        1.0,
        1.16,
    )

    context[
        "offense"
    ] = {
        "impact": round(
            offense_impact,
            2,
        ),

        "factor": round(
            offense_factor,
            3,
        ),

        "passing_impact": round(
            passing_impact,
            2,
        ),

        "passing_factor": round(
            passing_factor,
            3,
        ),

        "rushing_impact": round(
            rushing_impact,
            2,
        ),

        "rushing_factor": round(
            rushing_factor,
            3,
        ),
    }

    context[
        "defense"
    ] = {
        "impact": round(
            defense_impact,
            2,
        ),

        "factor": round(
            defense_factor,
            3,
        ),

        "pass_defense_impact": round(
            pass_defense_impact,
            2,
        ),

        "pass_defense_factor": round(
            pass_defense_factor,
            3,
        ),

        "rush_defense_impact": round(
            rush_defense_impact,
            2,
        ),

        "rush_defense_factor": round(
            rush_defense_factor,
            3,
        ),
    }

    context[
        "key_absences"
    ].sort(
        key=lambda row: f(
            row.get(
                "impact"
            )
        ),
        reverse=True,
    )

    context[
        "injuries"
    ].sort(
        key=lambda row: (
            -f(
                row.get(
                    "impact"
                )
            ),
            row.get(
                "player",
                "",
            ),
        )
    )

    return context


# =========================================================
# BUILD TEAM CONTEXTS
# =========================================================

def build_team_contexts(
    injury_rows: list[
        dict[str, Any]
    ],
    roster_by_id: dict[str, Any],
    roster_by_name: dict[str, Any],
    player_metrics: dict[str, Any],
):
    teams: dict[
        str,
        dict[str, Any]
    ] = {}

    normalized_injuries = []

    for row in injury_rows:
        if not isinstance(
            row,
            dict,
        ):
            continue

        injury = normalize_injury(
            row,
            roster_by_id,
            roster_by_name,
            player_metrics,
        )

        team = injury.get(
            "team"
        )

        if not team:
            continue

        # Ignore rows with no actual
        # injury designation/impact.
        if (
            not injury.get(
                "status"
            )
            and not injury.get(
                "practice_status"
            )
        ):
            continue

        normalized_injuries.append(
            injury
        )

        if team not in teams:
            teams[
                team
            ] = empty_team_context(
                team
            )

        add_injury_to_team(
            teams[
                team
            ],
            injury,
        )

    for team in list(
        teams.keys()
    ):
        teams[
            team
        ] = finalize_team_context(
            teams[
                team
            ]
        )

    return (
        teams,
        normalized_injuries,
    )


# =========================================================
# GAME CONTEXT
# =========================================================

def neutral_team_context(
    team: str,
):
    return finalize_team_context(
        empty_team_context(
            team
        )
    )


def build_game_context(
    game: dict[str, Any],
    team_contexts: dict[
        str,
        dict[str, Any]
    ],
):
    away_team = normalize_team(
        game.get(
            "away_team"
        )
        or game.get(
            "away"
        )
    )

    home_team = normalize_team(
        game.get(
            "home_team"
        )
        or game.get(
            "home"
        )
    )

    away = team_contexts.get(
        away_team
    )

    home = team_contexts.get(
        home_team
    )

    if not away:
        away = neutral_team_context(
            away_team
        )

    if not home:
        home = neutral_team_context(
            home_team
        )

    # Net offensive multipliers combine:
    #
    # own offensive injuries
    # +
    # opponent defensive injuries.

    away_scoring_factor = (
        f(
            away[
                "offense"
            ][
                "factor"
            ],
            1.0,
        )
        *
        f(
            home[
                "defense"
            ][
                "factor"
            ],
            1.0,
        )
    )

    home_scoring_factor = (
        f(
            home[
                "offense"
            ][
                "factor"
            ],
            1.0,
        )
        *
        f(
            away[
                "defense"
            ][
                "factor"
            ],
            1.0,
        )
    )

    away_passing_factor = (
        f(
            away[
                "offense"
            ][
                "passing_factor"
            ],
            1.0,
        )
        *
        f(
            home[
                "defense"
            ][
                "pass_defense_factor"
            ],
            1.0,
        )
    )

    home_passing_factor = (
        f(
            home[
                "offense"
            ][
                "passing_factor"
            ],
            1.0,
        )
        *
        f(
            away[
                "defense"
            ][
                "pass_defense_factor"
            ],
            1.0,
        )
    )

    away_rushing_factor = (
        f(
            away[
                "offense"
            ][
                "rushing_factor"
            ],
            1.0,
        )
        *
        f(
            home[
                "defense"
            ][
                "rush_defense_factor"
            ],
            1.0,
        )
    )

    home_rushing_factor = (
        f(
            home[
                "offense"
            ][
                "rushing_factor"
            ],
            1.0,
        )
        *
        f(
            away[
                "defense"
            ][
                "rush_defense_factor"
            ],
            1.0,
        )
    )

    game_id = (
        game.get(
            "game_id"
        )
        or game.get(
            "id"
        )
        or game.get(
            "espn_id"
        )
        or ""
    )

    return {
        "game_id": game_id,

        "away_team": away_team,
        "home_team": home_team,

        "away": {
            "team_context": away,

            "scoring_factor": round(
                clamp(
                    away_scoring_factor,
                    0.78,
                    1.18,
                ),
                3,
            ),

            "passing_factor": round(
                clamp(
                    away_passing_factor,
                    0.75,
                    1.20,
                ),
                3,
            ),

            "rushing_factor": round(
                clamp(
                    away_rushing_factor,
                    0.78,
                    1.18,
                ),
                3,
            ),
        },

        "home": {
            "team_context": home,

            "scoring_factor": round(
                clamp(
                    home_scoring_factor,
                    0.78,
                    1.18,
                ),
                3,
            ),

            "passing_factor": round(
                clamp(
                    home_passing_factor,
                    0.75,
                    1.20,
                ),
                3,
            ),

            "rushing_factor": round(
                clamp(
                    home_rushing_factor,
                    0.78,
                    1.18,
                ),
                3,
            ),
        },
    }


# =========================================================
# BUILD SLATE
# =========================================================

def build_slate_context(
    slate_file: Path,
    output_file: Path,
    web_output_file: Path,
    team_contexts: dict[
        str,
        dict[str, Any]
    ],
):
    slate_payload = load_json(
        slate_file,
        default={},
    )

    games = (
        slate_payload
        if isinstance(
            slate_payload,
            list,
        )
        else slate_payload.get(
            "games",
            [],
        )
        if isinstance(
            slate_payload,
            dict,
        )
        else []
    )

    output_games = []

    for game in games:
        if not isinstance(
            game,
            dict,
        ):
            continue

        context = build_game_context(
            game,
            team_contexts,
        )

        output_games.append(
            context
        )

        # Attach to slate for downstream
        # projection models.

        game[
            "injury_context"
        ] = {
            "away": {
                "scoring_factor": (
                    context[
                        "away"
                    ][
                        "scoring_factor"
                    ]
                ),

                "passing_factor": (
                    context[
                        "away"
                    ][
                        "passing_factor"
                    ]
                ),

                "rushing_factor": (
                    context[
                        "away"
                    ][
                        "rushing_factor"
                    ]
                ),

                "key_absences": (
                    context[
                        "away"
                    ][
                        "team_context"
                    ][
                        "key_absences"
                    ]
                ),
            },

            "home": {
                "scoring_factor": (
                    context[
                        "home"
                    ][
                        "scoring_factor"
                    ]
                ),

                "passing_factor": (
                    context[
                        "home"
                    ][
                        "passing_factor"
                    ]
                ),

                "rushing_factor": (
                    context[
                        "home"
                    ][
                        "rushing_factor"
                    ]
                ),

                "key_absences": (
                    context[
                        "home"
                    ][
                        "team_context"
                    ][
                        "key_absences"
                    ]
                ),
            },
        }

    payload = {
        "games": output_games,

        "teams": team_contexts,
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

    save_json(
        slate_payload,
        slate_file,
    )

    print(
        f"   ✅ {len(output_games)} "
        f"game injury contexts"
    )

    return payload


# =========================================================
# MAIN
# =========================================================

def build_nfl_injury_context():
    print(
        "\n🏥 BUILDING NFL "
        "INJURY CONTEXT\n"
    )

    injury_payload = load_json(
        INJURY_FILE,
        default=[],
    )

    roster_payload = load_json(
        ROSTERS_FILE,
        default=[],
    )

    player_metric_payload = load_json(
        PLAYER_METRICS_FILE,
        default={},
    )

    injury_rows = extract_list(
        injury_payload,
        "injuries",
        "players",
        "reports",
    )

    roster_by_id, roster_by_name = (
        build_roster_lookup(
            roster_payload
        )
    )

    player_metric_lookup = (
        build_player_metric_lookup(
            player_metric_payload
        )
    )

    print(
        f"   Injury rows: "
        f"{len(injury_rows)}"
    )

    print(
        f"   Roster players: "
        f"{len(roster_by_id)}"
    )

    print(
        f"   Player metrics: "
        f"{len(player_metric_lookup)}"
    )

    team_contexts, normalized_injuries = (
        build_team_contexts(
            injury_rows,
            roster_by_id,
            roster_by_name,
            player_metric_lookup,
        )
    )

    print(
        f"   Teams with injury data: "
        f"{len(team_contexts)}"
    )

    print(
        f"   Relevant injuries: "
        f"{len(normalized_injuries)}"
    )

    if not SLATE_FILE.exists():
        raise RuntimeError(
            f"NFL slate not found: "
            f"{SLATE_FILE}"
        )

    print(
        "\n   Current slate"
    )

    build_slate_context(
        SLATE_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
        team_contexts,
    )

    if NEXT_SLATE_FILE.exists():
        print(
            "\n   Next slate"
        )

        build_slate_context(
            NEXT_SLATE_FILE,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
            team_contexts,
        )

    print(
        "\n✅ NFL INJURY "
        "CONTEXT COMPLETE\n"
    )

    return {
        "teams": team_contexts,
        "injuries": normalized_injuries,
    }


if __name__ == "__main__":
    build_nfl_injury_context()
