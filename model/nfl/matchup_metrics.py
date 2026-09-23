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

TEAM_METRICS_FILE = (
    NFL_DIR
    / "team_metrics.json"
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

OUTPUT_FILE = (
    NFL_DIR
    / "matchup_metrics.json"
)

NEXT_OUTPUT_FILE = (
    NFL_DIR
    / "next"
    / "matchup_metrics.json"
)

WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "matchup_metrics.json"
)

NEXT_WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "next"
    / "matchup_metrics.json"
)


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


def nested(
    payload: dict[str, Any],
    *keys: str,
    default=0.0,
):
    current: Any = payload

    for key in keys:
        if not isinstance(
            current,
            dict,
        ):
            return default

        current = current.get(
            key
        )

        if current is None:
            return default

    return current


def round_value(
    value: Any,
    digits: int = 3,
):
    return round(
        f(value),
        digits,
    )


# =========================================================
# TEAM METRIC LOOKUP
# =========================================================

def build_team_lookup(
    payload: Any,
):
    lookup: dict[
        str,
        dict[str, Any]
    ] = {}

    if isinstance(
        payload,
        dict,
    ):
        teams = payload.get(
            "teams",
            [],
        )

        if not teams:
            teams = []

            for key, value in (
                payload.items()
            ):
                if not isinstance(
                    value,
                    dict,
                ):
                    continue

                item = dict(
                    value
                )

                item.setdefault(
                    "team",
                    key,
                )

                teams.append(
                    item
                )

    elif isinstance(
        payload,
        list,
    ):
        teams = payload

    else:
        teams = []

    for row in teams:
        if not isinstance(
            row,
            dict,
        ):
            continue

        team = normalize_team(
            row.get(
                "team"
            )
        )

        if not team:
            continue

        lookup[
            team
        ] = row

    return lookup


# =========================================================
# LEAGUE BASELINES
# =========================================================

def average(
    values: list[float],
):
    valid = [
        value
        for value in values
        if value is not None
    ]

    if not valid:
        return 0.0

    return (
        sum(valid)
        / len(valid)
    )


def build_league_baselines(
    team_lookup: dict[
        str,
        dict[str, Any]
    ],
):
    offense_rows = []

    defense_rows = []

    for team in (
        team_lookup.values()
    ):
        offense = team.get(
            "offense",
            {},
        )

        defense = team.get(
            "defense",
            {},
        )

        if offense:
            offense_rows.append(
                offense
            )

        if defense:
            defense_rows.append(
                defense
            )

    def avg_metric(
        rows,
        *path,
    ):
        return average(
            [
                f(
                    nested(
                        row,
                        *path,
                        default=0,
                    )
                )
                for row in rows
            ]
        )

    return {
        "offense": {
            "yards_per_play": (
                avg_metric(
                    offense_rows,
                    "yards_per_play",
                )
            ),

            "epa_per_play": (
                avg_metric(
                    offense_rows,
                    "epa_per_play",
                )
            ),

            "success_rate": (
                avg_metric(
                    offense_rows,
                    "success_rate",
                )
            ),

            "explosive_rate": (
                avg_metric(
                    offense_rows,
                    "explosive_rate",
                )
            ),

            "pass_epa": (
                avg_metric(
                    offense_rows,
                    "pass",
                    "epa_per_play",
                )
            ),

            "pass_success": (
                avg_metric(
                    offense_rows,
                    "pass",
                    "success_rate",
                )
            ),

            "pass_explosive": (
                avg_metric(
                    offense_rows,
                    "pass",
                    "explosive_rate",
                )
            ),

            "rush_epa": (
                avg_metric(
                    offense_rows,
                    "rush",
                    "epa_per_play",
                )
            ),

            "rush_success": (
                avg_metric(
                    offense_rows,
                    "rush",
                    "success_rate",
                )
            ),

            "rush_explosive": (
                avg_metric(
                    offense_rows,
                    "rush",
                    "explosive_rate",
                )
            ),

            "third_down_rate": (
                avg_metric(
                    offense_rows,
                    "third_down_rate",
                )
            ),

            "red_zone_td_rate": (
                avg_metric(
                    offense_rows,
                    "red_zone_td_rate",
                )
            ),

            "turnovers_per_game": (
                avg_metric(
                    offense_rows,
                    "turnovers_per_game",
                )
            ),

            "sacks_per_game": (
                avg_metric(
                    offense_rows,
                    "sacks_per_game",
                )
            ),
        },

        "defense": {
            "yards_per_play": (
                avg_metric(
                    defense_rows,
                    "yards_per_play",
                )
            ),

            "epa_per_play": (
                avg_metric(
                    defense_rows,
                    "epa_per_play",
                )
            ),

            "success_rate": (
                avg_metric(
                    defense_rows,
                    "success_rate",
                )
            ),

            "explosive_rate": (
                avg_metric(
                    defense_rows,
                    "explosive_rate",
                )
            ),

            "pass_epa": (
                avg_metric(
                    defense_rows,
                    "pass",
                    "epa_per_play",
                )
            ),

            "pass_success": (
                avg_metric(
                    defense_rows,
                    "pass",
                    "success_rate",
                )
            ),

            "pass_explosive": (
                avg_metric(
                    defense_rows,
                    "pass",
                    "explosive_rate",
                )
            ),

            "rush_epa": (
                avg_metric(
                    defense_rows,
                    "rush",
                    "epa_per_play",
                )
            ),

            "rush_success": (
                avg_metric(
                    defense_rows,
                    "rush",
                    "success_rate",
                )
            ),

            "rush_explosive": (
                avg_metric(
                    defense_rows,
                    "rush",
                    "explosive_rate",
                )
            ),

            "third_down_rate": (
                avg_metric(
                    defense_rows,
                    "third_down_rate",
                )
            ),

            "red_zone_td_rate": (
                avg_metric(
                    defense_rows,
                    "red_zone_td_rate",
                )
            ),

            "turnovers_per_game": (
                avg_metric(
                    defense_rows,
                    "turnovers_per_game",
                )
            ),

            "sacks_per_game": (
                avg_metric(
                    defense_rows,
                    "sacks_per_game",
                )
            ),
        },
    }


# =========================================================
# MATCHUP EDGE FUNCTIONS
# =========================================================

def differential_edge(
    offense_value: Any,
    defense_value: Any,
    offense_baseline: Any,
    defense_baseline: Any,
    scale: float,
):
    """
    Positive = advantage for offense.
    Negative = advantage for defense.

    We compare:
        offense vs league-average offense

    plus:
        opponent defense allowed
        vs league-average defense allowed

    Since defensive metrics represent what the
    defense ALLOWS, higher defensive values are
    generally favorable for the offense.
    """

    offense_delta = (
        f(offense_value)
        - f(offense_baseline)
    )

    defense_delta = (
        f(defense_value)
        - f(defense_baseline)
    )

    raw = (
        offense_delta
        + defense_delta
    )

    return clamp(
        raw * scale,
        -100,
        100,
    )


def inverse_edge(
    offense_value: Any,
    defense_value: Any,
    offense_baseline: Any,
    defense_baseline: Any,
    scale: float,
):
    """
    Used for metrics where LOWER is better
    for the offense, such as turnovers.

    Positive = advantage for offense.
    """

    offense_delta = (
        f(offense_baseline)
        - f(offense_value)
    )

    defense_delta = (
        f(defense_value)
        - f(defense_baseline)
    )

    raw = (
        offense_delta
        + defense_delta
    )

    return clamp(
        raw * scale,
        -100,
        100,
    )


def weighted_score(
    values: list[
        tuple[
            float,
            float,
        ]
    ],
):
    total_weight = sum(
        weight
        for _,
        weight in values
    )

    if not total_weight:
        return 0.0

    return sum(
        value * weight
        for value,
        weight in values
    ) / total_weight


def rating_label(
    score: float,
):
    if score >= 30:
        return "Elite"

    if score >= 15:
        return "Strong"

    if score >= 5:
        return "Favorable"

    if score > -5:
        return "Neutral"

    if score > -15:
        return "Difficult"

    if score > -30:
        return "Poor"

    return "Severe"


# =========================================================
# OFFENSE VS DEFENSE MATCHUP
# =========================================================

def build_offense_matchup(
    offense_team: str,
    defense_team: str,
    team_lookup: dict[
        str,
        dict[str, Any]
    ],
    league: dict[
        str,
        Any
    ],
):
    offense_team = normalize_team(
        offense_team
    )

    defense_team = normalize_team(
        defense_team
    )

    offense_row = (
        team_lookup.get(
            offense_team,
            {},
        )
    )

    defense_row = (
        team_lookup.get(
            defense_team,
            {},
        )
    )

    offense = offense_row.get(
        "offense",
        {},
    )

    defense = defense_row.get(
        "defense",
        {},
    )

    league_offense = league[
        "offense"
    ]

    league_defense = league[
        "defense"
    ]

    # -----------------------------------------------------
    # OVERALL EPA
    # -----------------------------------------------------

    epa_edge = differential_edge(
        nested(
            offense,
            "epa_per_play",
        ),
        nested(
            defense,
            "epa_per_play",
        ),
        league_offense[
            "epa_per_play"
        ],
        league_defense[
            "epa_per_play"
        ],
        180,
    )

    # -----------------------------------------------------
    # YARDS / PLAY
    # -----------------------------------------------------

    yards_edge = differential_edge(
        nested(
            offense,
            "yards_per_play",
        ),
        nested(
            defense,
            "yards_per_play",
        ),
        league_offense[
            "yards_per_play"
        ],
        league_defense[
            "yards_per_play"
        ],
        12,
    )

    # -----------------------------------------------------
    # SUCCESS RATE
    # -----------------------------------------------------

    success_edge = differential_edge(
        nested(
            offense,
            "success_rate",
        ),
        nested(
            defense,
            "success_rate",
        ),
        league_offense[
            "success_rate"
        ],
        league_defense[
            "success_rate"
        ],
        2.5,
    )

    # -----------------------------------------------------
    # EXPLOSIVE PLAY RATE
    # -----------------------------------------------------

    explosive_edge = (
        differential_edge(
            nested(
                offense,
                "explosive_rate",
            ),
            nested(
                defense,
                "explosive_rate",
            ),
            league_offense[
                "explosive_rate"
            ],
            league_defense[
                "explosive_rate"
            ],
            4,
        )
    )

    # -----------------------------------------------------
    # PASSING MATCHUP
    # -----------------------------------------------------

    pass_epa_edge = (
        differential_edge(
            nested(
                offense,
                "pass",
                "epa_per_play",
            ),
            nested(
                defense,
                "pass",
                "epa_per_play",
            ),
            league_offense[
                "pass_epa"
            ],
            league_defense[
                "pass_epa"
            ],
            170,
        )
    )

    pass_success_edge = (
        differential_edge(
            nested(
                offense,
                "pass",
                "success_rate",
            ),
            nested(
                defense,
                "pass",
                "success_rate",
            ),
            league_offense[
                "pass_success"
            ],
            league_defense[
                "pass_success"
            ],
            2.2,
        )
    )

    pass_explosive_edge = (
        differential_edge(
            nested(
                offense,
                "pass",
                "explosive_rate",
            ),
            nested(
                defense,
                "pass",
                "explosive_rate",
            ),
            league_offense[
                "pass_explosive"
            ],
            league_defense[
                "pass_explosive"
            ],
            3.5,
        )
    )

    passing_score = (
        weighted_score(
            [
                (
                    pass_epa_edge,
                    0.50,
                ),
                (
                    pass_success_edge,
                    0.30,
                ),
                (
                    pass_explosive_edge,
                    0.20,
                ),
            ]
        )
    )

    # -----------------------------------------------------
    # RUSHING MATCHUP
    # -----------------------------------------------------

    rush_epa_edge = (
        differential_edge(
            nested(
                offense,
                "rush",
                "epa_per_play",
            ),
            nested(
                defense,
                "rush",
                "epa_per_play",
            ),
            league_offense[
                "rush_epa"
            ],
            league_defense[
                "rush_epa"
            ],
            170,
        )
    )

    rush_success_edge = (
        differential_edge(
            nested(
                offense,
                "rush",
                "success_rate",
            ),
            nested(
                defense,
                "rush",
                "success_rate",
            ),
            league_offense[
                "rush_success"
            ],
            league_defense[
                "rush_success"
            ],
            2.2,
        )
    )

    rush_explosive_edge = (
        differential_edge(
            nested(
                offense,
                "rush",
                "explosive_rate",
            ),
            nested(
                defense,
                "rush",
                "explosive_rate",
            ),
            league_offense[
                "rush_explosive"
            ],
            league_defense[
                "rush_explosive"
            ],
            3.5,
        )
    )

    rushing_score = (
        weighted_score(
            [
                (
                    rush_epa_edge,
                    0.50,
                ),
                (
                    rush_success_edge,
                    0.30,
                ),
                (
                    rush_explosive_edge,
                    0.20,
                ),
            ]
        )
    )

    # -----------------------------------------------------
    # THIRD DOWN
    # -----------------------------------------------------

    third_down_edge = (
        differential_edge(
            nested(
                offense,
                "third_down_rate",
            ),
            nested(
                defense,
                "third_down_rate",
            ),
            league_offense[
                "third_down_rate"
            ],
            league_defense[
                "third_down_rate"
            ],
            2,
        )
    )

    # -----------------------------------------------------
    # RED ZONE
    # -----------------------------------------------------

    red_zone_edge = (
        differential_edge(
            nested(
                offense,
                "red_zone_td_rate",
            ),
            nested(
                defense,
                "red_zone_td_rate",
            ),
            league_offense[
                "red_zone_td_rate"
            ],
            league_defense[
                "red_zone_td_rate"
            ],
            1.5,
        )
    )

    # -----------------------------------------------------
    # TURNOVERS
    # -----------------------------------------------------

    turnover_edge = inverse_edge(
        nested(
            offense,
            "turnovers_per_game",
        ),
        nested(
            defense,
            "turnovers_per_game",
        ),
        league_offense[
            "turnovers_per_game"
        ],
        league_defense[
            "turnovers_per_game"
        ],
        15,
    )

    # -----------------------------------------------------
    # OVERALL MATCHUP
    # -----------------------------------------------------

    overall_score = (
        weighted_score(
            [
                (
                    epa_edge,
                    0.22,
                ),
                (
                    success_edge,
                    0.14,
                ),
                (
                    yards_edge,
                    0.10,
                ),
                (
                    explosive_edge,
                    0.10,
                ),
                (
                    passing_score,
                    0.18,
                ),
                (
                    rushing_score,
                    0.10,
                ),
                (
                    third_down_edge,
                    0.06,
                ),
                (
                    red_zone_edge,
                    0.06,
                ),
                (
                    turnover_edge,
                    0.04,
                ),
            ]
        )
    )

    overall_score = round(
        clamp(
            overall_score,
            -100,
            100,
        ),
        1,
    )

    return {
        "offense_team": (
            offense_team
        ),

        "defense_team": (
            defense_team
        ),

        "rating": (
            overall_score
        ),

        "rating_label": (
            rating_label(
                overall_score
            )
        ),

        "overall": {
            "epa_edge": round(
                epa_edge,
                1,
            ),

            "success_edge": round(
                success_edge,
                1,
            ),

            "yards_per_play_edge": round(
                yards_edge,
                1,
            ),

            "explosive_edge": round(
                explosive_edge,
                1,
            ),

            "third_down_edge": round(
                third_down_edge,
                1,
            ),

            "red_zone_edge": round(
                red_zone_edge,
                1,
            ),

            "turnover_edge": round(
                turnover_edge,
                1,
            ),
        },

        "passing": {
            "rating": round(
                passing_score,
                1,
            ),

            "rating_label": (
                rating_label(
                    passing_score
                )
            ),

            "epa_edge": round(
                pass_epa_edge,
                1,
            ),

            "success_edge": round(
                pass_success_edge,
                1,
            ),

            "explosive_edge": round(
                pass_explosive_edge,
                1,
            ),
        },

        "rushing": {
            "rating": round(
                rushing_score,
                1,
            ),

            "rating_label": (
                rating_label(
                    rushing_score
                )
            ),

            "epa_edge": round(
                rush_epa_edge,
                1,
            ),

            "success_edge": round(
                rush_success_edge,
                1,
            ),

            "explosive_edge": round(
                rush_explosive_edge,
                1,
            ),
        },

        "raw": {
            "offense": {
                "epa_per_play": (
                    round_value(
                        nested(
                            offense,
                            "epa_per_play",
                        )
                    )
                ),

                "yards_per_play": (
                    round_value(
                        nested(
                            offense,
                            "yards_per_play",
                        ),
                        2,
                    )
                ),

                "success_rate": (
                    round_value(
                        nested(
                            offense,
                            "success_rate",
                        ),
                        1,
                    )
                ),

                "explosive_rate": (
                    round_value(
                        nested(
                            offense,
                            "explosive_rate",
                        ),
                        1,
                    )
                ),
            },

            "defense_allowed": {
                "epa_per_play": (
                    round_value(
                        nested(
                            defense,
                            "epa_per_play",
                        )
                    )
                ),

                "yards_per_play": (
                    round_value(
                        nested(
                            defense,
                            "yards_per_play",
                        ),
                        2,
                    )
                ),

                "success_rate": (
                    round_value(
                        nested(
                            defense,
                            "success_rate",
                        ),
                        1,
                    )
                ),

                "explosive_rate": (
                    round_value(
                        nested(
                            defense,
                            "explosive_rate",
                        ),
                        1,
                    )
                ),
            },
        },
    }


# =========================================================
# GAME
# =========================================================

def build_game_matchup(
    game: dict[str, Any],
    team_lookup: dict[
        str,
        dict[str, Any]
    ],
    league: dict[
        str,
        Any
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

    away_matchup = (
        build_offense_matchup(
            away_team,
            home_team,
            team_lookup,
            league,
        )
    )

    home_matchup = (
        build_offense_matchup(
            home_team,
            away_team,
            team_lookup,
            league,
        )
    )

    away_rating = f(
        away_matchup.get(
            "rating"
        )
    )

    home_rating = f(
        home_matchup.get(
            "rating"
        )
    )

    matchup_differential = (
        away_rating
        - home_rating
    )

    if (
        matchup_differential
        > 3
    ):
        matchup_advantage = (
            away_team
        )

    elif (
        matchup_differential
        < -3
    ):
        matchup_advantage = (
            home_team
        )

    else:
        matchup_advantage = (
            "EVEN"
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
        "game_id": (
            game_id
        ),

        "away_team": (
            away_team
        ),

        "home_team": (
            home_team
        ),

        "away": (
            away_matchup
        ),

        "home": (
            home_matchup
        ),

        "matchup_differential": round(
            matchup_differential,
            1,
        ),

        "matchup_advantage": (
            matchup_advantage
        ),
    }


# =========================================================
# BUILD FILE
# =========================================================

def build_matchup_file(
    slate_file: Path,
    output_file: Path,
    web_output_file: Path,
    team_lookup: dict[
        str,
        dict[str, Any]
    ],
    league: dict[
        str,
        Any
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
    )

    matchups = []

    for game in games:
        if not isinstance(
            game,
            dict,
        ):
            continue

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

        if (
            not away_team
            or not home_team
        ):
            continue

        if (
            away_team
            not in team_lookup
        ):
            print(
                f"   ⚠️ Missing team "
                f"metrics: {away_team}"
            )

        if (
            home_team
            not in team_lookup
        ):
            print(
                f"   ⚠️ Missing team "
                f"metrics: {home_team}"
            )

        matchup = (
            build_game_matchup(
                game,
                team_lookup,
                league,
            )
        )

        matchups.append(
            matchup
        )

        # Attach the same information directly
        # to the slate so later NFL model layers
        # don't have to join another file.
        game[
            "matchup_metrics"
        ] = {
            "away": (
                matchup[
                    "away"
                ]
            ),

            "home": (
                matchup[
                    "home"
                ]
            ),

            "matchup_differential": (
                matchup[
                    "matchup_differential"
                ]
            ),

            "matchup_advantage": (
                matchup[
                    "matchup_advantage"
                ]
            ),
        }

    payload = {
        "games": matchups,
        "league_baselines": (
            league
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

    # Also save the enriched slate.
    save_json(
        slate_payload,
        slate_file,
    )

    print(
        f"   ✅ {len(matchups)} "
        f"matchups"
    )

    print(
        f"      {output_file}"
    )

    print(
        f"      {web_output_file}"
    )

    return payload


# =========================================================
# MAIN
# =========================================================

def build_nfl_matchup_metrics():
    print(
        "\n⚔️ BUILDING NFL "
        "MATCHUP METRICS\n"
    )

    team_payload = load_json(
        TEAM_METRICS_FILE,
        default=[],
    )

    team_lookup = (
        build_team_lookup(
            team_payload
        )
    )

    if not team_lookup:
        raise RuntimeError(
            "No NFL team metrics found. "
            "Run model.nfl.team_metrics first."
        )

    print(
        f"   Team profiles: "
        f"{len(team_lookup)}"
    )

    league = (
        build_league_baselines(
            team_lookup
        )
    )

    print(
        "\n   Current slate"
    )

    build_matchup_file(
        SLATE_FILE,
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
        team_lookup,
        league,
    )

    if (
        NEXT_SLATE_FILE.exists()
    ):
        print(
            "\n   Next slate"
        )

        build_matchup_file(
            NEXT_SLATE_FILE,
            NEXT_OUTPUT_FILE,
            NEXT_WEB_OUTPUT_FILE,
            team_lookup,
            league,
        )

    print(
        "\n✅ NFL MATCHUP "
        "METRICS COMPLETE\n"
    )


if __name__ == "__main__":
    build_nfl_matchup_metrics()
