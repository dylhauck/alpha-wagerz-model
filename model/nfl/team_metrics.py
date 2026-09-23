from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import nflreadpy as nfl

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

TEAMS_FILE = (
    NFL_DIR
    / "teams.json"
)

OUTPUT_FILE = (
    NFL_DIR
    / "team_metrics.json"
)

WEB_OUTPUT_FILE = (
    WEB_NFL_DIR
    / "team_metrics.json"
)

CURRENT_SEASON = 2026
BASELINE_SEASON = 2025

# Number of current-season games before
# we essentially trust current-year data fully.
FULL_CURRENT_WEIGHT_GAMES = 8

EXPLOSIVE_PASS_YARDS = 20
EXPLOSIVE_RUSH_YARDS = 10


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


def truthy(
    value: Any,
) -> bool:
    if isinstance(
        value,
        bool,
    ):
        return value

    return f(
        value
    ) > 0


def polars_records(
    frame,
) -> list[
    dict[str, Any]
]:
    if frame is None:
        return []

    try:
        rows = (
            frame.to_dicts()
        )
    except Exception:
        return []

    cleaned = []

    for row in rows:
        cleaned_row = {}

        for key, value in (
            row.items()
        ):
            if hasattr(
                value,
                "item",
            ):
                try:
                    value = (
                        value.item()
                    )
                except Exception:
                    pass

            if hasattr(
                value,
                "isoformat",
            ):
                try:
                    value = (
                        value.isoformat()
                    )
                except Exception:
                    pass

            cleaned_row[
                key
            ] = value

        cleaned.append(
            cleaned_row
        )

    return cleaned


def load_pbp(
    season: int,
) -> list[
    dict[str, Any]
]:
    print(
        f"   Loading {season} "
        f"play-by-play..."
    )

    try:
        frame = nfl.load_pbp(
            [season]
        )

        rows = polars_records(
            frame
        )

        print(
            f"   ✅ {season}: "
            f"{len(rows)} plays"
        )

        return rows

    except Exception as exc:
        print(
            f"   ⚠️ {season} "
            f"play-by-play unavailable: "
            f"{exc}"
        )

        return []


def regular_season_play(
    row: dict[
        str,
        Any,
    ],
) -> bool:
    season_type = (
        clean_text(
            row.get(
                "season_type"
            )
        ).upper()
    )

    return season_type in {
        "",
        "REG",
    }


def valid_scrimmage_play(
    row: dict[
        str,
        Any,
    ],
) -> bool:
    if not regular_season_play(
        row
    ):
        return False

    posteam = normalize_team(
        row.get(
            "posteam"
        )
    )

    defteam = normalize_team(
        row.get(
            "defteam"
        )
    )

    if (
        not posteam
        or not defteam
    ):
        return False

    play_type = clean_text(
        row.get(
            "play_type"
        )
    ).lower()

    if play_type not in {
        "pass",
        "run",
    }:
        return False

    return True


def empty_metrics():
    return {
        "plays": 0,
        "pass_plays": 0,
        "rush_plays": 0,

        "yards": 0.0,
        "pass_yards": 0.0,
        "rush_yards": 0.0,

        "epa": 0.0,
        "pass_epa": 0.0,
        "rush_epa": 0.0,

        "successes": 0,
        "pass_successes": 0,
        "rush_successes": 0,

        "explosive_plays": 0,
        "explosive_passes": 0,
        "explosive_rushes": 0,

        "touchdowns": 0,
        "pass_touchdowns": 0,
        "rush_touchdowns": 0,

        "turnovers": 0,
        "interceptions": 0,
        "fumbles_lost": 0,

        "sacks": 0,

        "third_down_attempts": 0,
        "third_down_conversions": 0,

        "red_zone_plays": 0,
        "red_zone_touchdowns": 0,

        "game_ids": set(),
    }


def add_play(
    metrics: dict[
        str,
        Any,
    ],
    row: dict[
        str,
        Any,
    ],
):
    play_type = clean_text(
        row.get(
            "play_type"
        )
    ).lower()

    yards = f(
        row.get(
            "yards_gained"
        )
    )

    epa = f(
        row.get(
            "epa"
        )
    )

    success = truthy(
        row.get(
            "success"
        )
    )

    touchdown = (
        truthy(
            row.get(
                "touchdown"
            )
        )
        or truthy(
            row.get(
                "pass_touchdown"
            )
        )
        or truthy(
            row.get(
                "rush_touchdown"
            )
        )
    )

    game_id = clean_text(
        row.get(
            "game_id"
        )
    )

    metrics[
        "plays"
    ] += 1

    metrics[
        "yards"
    ] += yards

    metrics[
        "epa"
    ] += epa

    if success:
        metrics[
            "successes"
        ] += 1

    if game_id:
        metrics[
            "game_ids"
        ].add(
            game_id
        )

    if (
        play_type
        == "pass"
    ):
        metrics[
            "pass_plays"
        ] += 1

        metrics[
            "pass_yards"
        ] += yards

        metrics[
            "pass_epa"
        ] += epa

        if success:
            metrics[
                "pass_successes"
            ] += 1

        if (
            yards
            >= EXPLOSIVE_PASS_YARDS
        ):
            metrics[
                "explosive_plays"
            ] += 1

            metrics[
                "explosive_passes"
            ] += 1

        if touchdown:
            metrics[
                "pass_touchdowns"
            ] += 1

    elif (
        play_type
        == "run"
    ):
        metrics[
            "rush_plays"
        ] += 1

        metrics[
            "rush_yards"
        ] += yards

        metrics[
            "rush_epa"
        ] += epa

        if success:
            metrics[
                "rush_successes"
            ] += 1

        if (
            yards
            >= EXPLOSIVE_RUSH_YARDS
        ):
            metrics[
                "explosive_plays"
            ] += 1

            metrics[
                "explosive_rushes"
            ] += 1

        if touchdown:
            metrics[
                "rush_touchdowns"
            ] += 1

    if touchdown:
        metrics[
            "touchdowns"
        ] += 1

    interception = truthy(
        row.get(
            "interception"
        )
    )

    fumble_lost = truthy(
        row.get(
            "fumble_lost"
        )
    )

    if interception:
        metrics[
            "interceptions"
        ] += 1

    if fumble_lost:
        metrics[
            "fumbles_lost"
        ] += 1

    if (
        interception
        or fumble_lost
    ):
        metrics[
            "turnovers"
        ] += 1

    if truthy(
        row.get(
            "sack"
        )
    ):
        metrics[
            "sacks"
        ] += 1

    down = int(
        f(
            row.get(
                "down"
            )
        )
    )

    if down == 3:
        metrics[
            "third_down_attempts"
        ] += 1

        converted = (
            truthy(
                row.get(
                    "third_down_converted"
                )
            )
            or (
                not truthy(
                    row.get(
                        "third_down_failed"
                    )
                )
                and (
                    epa > 0
                    or success
                )
            )
        )

        if converted:
            metrics[
                "third_down_conversions"
            ] += 1

    yardline_100 = f(
        row.get(
            "yardline_100"
        ),
        default=100,
    )

    if (
        0
        <= yardline_100
        <= 20
    ):
        metrics[
            "red_zone_plays"
        ] += 1

        if touchdown:
            metrics[
                "red_zone_touchdowns"
            ] += 1


def safe_rate(
    numerator: float,
    denominator: float,
    multiplier: float = 1.0,
    digits: int = 3,
):
    if not denominator:
        return 0.0

    return round(
        (
            numerator
            / denominator
        )
        * multiplier,
        digits,
    )


def finalize_metrics(
    raw: dict[
        str,
        Any,
    ],
):
    plays = max(
        1,
        raw[
            "plays"
        ],
    )

    pass_plays = max(
        1,
        raw[
            "pass_plays"
        ],
    )

    rush_plays = max(
        1,
        raw[
            "rush_plays"
        ],
    )

    games = len(
        raw[
            "game_ids"
        ]
    )

    games_divisor = max(
        1,
        games,
    )

    return {
        "games": games,

        "plays": raw[
            "plays"
        ],

        "plays_per_game": round(
            raw[
                "plays"
            ]
            / games_divisor,
            1,
        ),

        "yards_per_game": round(
            raw[
                "yards"
            ]
            / games_divisor,
            1,
        ),

        "yards_per_play": round(
            raw[
                "yards"
            ]
            / plays,
            2,
        ),

        "epa_per_play": round(
            raw[
                "epa"
            ]
            / plays,
            3,
        ),

        "success_rate": safe_rate(
            raw[
                "successes"
            ],
            raw[
                "plays"
            ],
            multiplier=100,
            digits=1,
        ),

        "explosive_rate": safe_rate(
            raw[
                "explosive_plays"
            ],
            raw[
                "plays"
            ],
            multiplier=100,
            digits=1,
        ),

        "pass": {
            "plays": raw[
                "pass_plays"
            ],

            "rate": safe_rate(
                raw[
                    "pass_plays"
                ],
                raw[
                    "plays"
                ],
                multiplier=100,
                digits=1,
            ),

            "yards_per_play": round(
                raw[
                    "pass_yards"
                ]
                / pass_plays,
                2,
            ),

            "epa_per_play": round(
                raw[
                    "pass_epa"
                ]
                / pass_plays,
                3,
            ),

            "success_rate": safe_rate(
                raw[
                    "pass_successes"
                ],
                raw[
                    "pass_plays"
                ],
                multiplier=100,
                digits=1,
            ),

            "explosive_rate": safe_rate(
                raw[
                    "explosive_passes"
                ],
                raw[
                    "pass_plays"
                ],
                multiplier=100,
                digits=1,
            ),

            "touchdowns": raw[
                "pass_touchdowns"
            ],
        },

        "rush": {
            "plays": raw[
                "rush_plays"
            ],

            "rate": safe_rate(
                raw[
                    "rush_plays"
                ],
                raw[
                    "plays"
                ],
                multiplier=100,
                digits=1,
            ),

            "yards_per_play": round(
                raw[
                    "rush_yards"
                ]
                / rush_plays,
                2,
            ),

            "epa_per_play": round(
                raw[
                    "rush_epa"
                ]
                / rush_plays,
                3,
            ),

            "success_rate": safe_rate(
                raw[
                    "rush_successes"
                ],
                raw[
                    "rush_plays"
                ],
                multiplier=100,
                digits=1,
            ),

            "explosive_rate": safe_rate(
                raw[
                    "explosive_rushes"
                ],
                raw[
                    "rush_plays"
                ],
                multiplier=100,
                digits=1,
            ),

            "touchdowns": raw[
                "rush_touchdowns"
            ],
        },

        "touchdowns": raw[
            "touchdowns"
        ],

        "touchdowns_per_game": round(
            raw[
                "touchdowns"
            ]
            / games_divisor,
            2,
        ),

        "turnovers": raw[
            "turnovers"
        ],

        "turnovers_per_game": round(
            raw[
                "turnovers"
            ]
            / games_divisor,
            2,
        ),

        "interceptions": raw[
            "interceptions"
        ],

        "fumbles_lost": raw[
            "fumbles_lost"
        ],

        "sacks": raw[
            "sacks"
        ],

        "sacks_per_game": round(
            raw[
                "sacks"
            ]
            / games_divisor,
            2,
        ),

        "third_down_rate": safe_rate(
            raw[
                "third_down_conversions"
            ],
            raw[
                "third_down_attempts"
            ],
            multiplier=100,
            digits=1,
        ),

        "red_zone_td_rate": safe_rate(
            raw[
                "red_zone_touchdowns"
            ],
            raw[
                "red_zone_plays"
            ],
            multiplier=100,
            digits=1,
        ),
    }


def build_season_profiles(
    rows: list[
        dict[str, Any]
    ],
):
    offense = defaultdict(
        empty_metrics
    )

    defense = defaultdict(
        empty_metrics
    )

    for row in rows:
        if not valid_scrimmage_play(
            row
        ):
            continue

        offense_team = normalize_team(
            row.get(
                "posteam"
            )
        )

        defense_team = normalize_team(
            row.get(
                "defteam"
            )
        )

        add_play(
            offense[
                offense_team
            ],
            row,
        )

        # Same play from the defense's
        # perspective. Offensive efficiency
        # allowed becomes defensive metrics.
        add_play(
            defense[
                defense_team
            ],
            row,
        )

    all_teams = set(
        offense.keys()
    ) | set(
        defense.keys()
    )

    output = {}

    for team in all_teams:
        output[
            team
        ] = {
            "offense": (
                finalize_metrics(
                    offense[
                        team
                    ]
                )
            ),

            "defense": (
                finalize_metrics(
                    defense[
                        team
                    ]
                )
            ),
        }

    return output


def blend_number(
    baseline: Any,
    current: Any,
    current_weight: float,
):
    baseline_number = f(
        baseline
    )

    current_number = f(
        current
    )

    return round(
        (
            baseline_number
            * (
                1
                - current_weight
            )
        )
        + (
            current_number
            * current_weight
        ),
        3,
    )


def blend_dict(
    baseline: dict[
        str,
        Any,
    ],
    current: dict[
        str,
        Any,
    ],
    current_weight: float,
):
    result = {}

    keys = (
        set(
            baseline.keys()
        )
        | set(
            current.keys()
        )
    )

    for key in keys:
        baseline_value = (
            baseline.get(
                key
            )
        )

        current_value = (
            current.get(
                key
            )
        )

        if (
            isinstance(
                baseline_value,
                dict,
            )
            or isinstance(
                current_value,
                dict,
            )
        ):
            result[
                key
            ] = blend_dict(
                baseline_value
                if isinstance(
                    baseline_value,
                    dict,
                )
                else {},
                current_value
                if isinstance(
                    current_value,
                    dict,
                )
                else {},
                current_weight,
            )

        elif key in {
            "games",
            "plays",
        }:
            result[
                key
            ] = (
                current_value
                if current_value
                is not None
                else baseline_value
            )

        elif isinstance(
            baseline_value,
            (
                int,
                float,
            ),
        ) or isinstance(
            current_value,
            (
                int,
                float,
            ),
        ):
            result[
                key
            ] = blend_number(
                baseline_value,
                current_value,
                current_weight,
            )

        else:
            result[
                key
            ] = (
                current_value
                if current_value
                not in (
                    None,
                    "",
                )
                else baseline_value
            )

    return result


def current_season_weight(
    games: int,
):
    if games <= 0:
        return 0.0

    return min(
        1.0,
        games
        / FULL_CURRENT_WEIGHT_GAMES,
    )


def team_codes():
    payload = load_json(
        TEAMS_FILE,
        default=[],
    )

    teams = (
        payload
        if isinstance(
            payload,
            list,
        )
        else payload.get(
            "teams",
            [],
        )
    )

    codes = set()

    for team in teams:
        if not isinstance(
            team,
            dict,
        ):
            continue

        code = normalize_team(
            team.get(
                "abbr"
            )
            or team.get(
                "team_abbr"
            )
            or team.get(
                "team"
            )
            or team.get(
                "abbreviation"
            )
        )

        if code:
            codes.add(
                code
            )

    return codes


def build_team_metrics():
    print(
        "\n🏈 BUILDING NFL "
        "TEAM METRICS\n"
    )

    baseline_rows = load_pbp(
        BASELINE_SEASON
    )

    current_rows = load_pbp(
        CURRENT_SEASON
    )

    baseline_profiles = (
        build_season_profiles(
            baseline_rows
        )
    )

    current_profiles = (
        build_season_profiles(
            current_rows
        )
    )

    teams = (
        team_codes()
        | set(
            baseline_profiles.keys()
        )
        | set(
            current_profiles.keys()
        )
    )

    output = []

    for team in sorted(
        teams
    ):
        baseline = (
            baseline_profiles.get(
                team,
                {},
            )
        )

        current = (
            current_profiles.get(
                team,
                {},
            )
        )

        current_games = int(
            f(
                current.get(
                    "offense",
                    {},
                ).get(
                    "games"
                )
            )
        )

        weight = (
            current_season_weight(
                current_games
            )
        )

        baseline_offense = (
            baseline.get(
                "offense",
                {},
            )
        )

        baseline_defense = (
            baseline.get(
                "defense",
                {},
            )
        )

        current_offense = (
            current.get(
                "offense",
                {},
            )
        )

        current_defense = (
            current.get(
                "defense",
                {},
            )
        )

        if current_games > 0:
            offense = blend_dict(
                baseline_offense,
                current_offense,
                weight,
            )

            defense = blend_dict(
                baseline_defense,
                current_defense,
                weight,
            )

        else:
            offense = (
                baseline_offense
            )

            defense = (
                baseline_defense
            )

        output.append(
            {
                "team": team,

                "model_season": (
                    CURRENT_SEASON
                ),

                "baseline_season": (
                    BASELINE_SEASON
                ),

                "current_games": (
                    current_games
                ),

                "current_season_weight": round(
                    weight,
                    3,
                ),

                "baseline_weight": round(
                    1.0
                    - weight,
                    3,
                ),

                "offense": offense,
                "defense": defense,

                "raw": {
                    str(
                        BASELINE_SEASON
                    ): baseline,

                    str(
                        CURRENT_SEASON
                    ): current,
                },
            }
        )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    WEB_OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(
        output,
        OUTPUT_FILE,
    )

    save_json(
        output,
        WEB_OUTPUT_FILE,
    )

    print(
        "✅ team_metrics.json"
    )

    print(
        f"   model: "
        f"{OUTPUT_FILE}"
    )

    print(
        f"   web:   "
        f"{WEB_OUTPUT_FILE}"
    )

    print(
        f"   teams: "
        f"{len(output)}"
    )

    print(
        "\n✅ NFL TEAM METRICS "
        "COMPLETE\n"
    )

    return output


if __name__ == "__main__":
    build_team_metrics()
