from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from nba_api.stats.endpoints import leaguestandings


MODEL_ROOT = Path(__file__).resolve().parents[2]

NBA_DIR = (
    MODEL_ROOT
    / "data"
    / "processed"
    / "nba"
)

WEB_NBA_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nba"
)

OUTPUT_FILE = (
    NBA_DIR
    / "team_rankings.json"
)

WEB_OUTPUT_FILE = (
    WEB_NBA_DIR
    / "team_rankings.json"
)

CURRENT_SEASON = "2026-27"

CENTRAL = ZoneInfo(
    "America/Chicago"
)


def clean_text(
    value: Any,
) -> str:
    return str(
        value or ""
    ).strip()


def number(
    value: Any,
    default=0,
):
    try:
        if value in (
            None,
            "",
        ):
            return default

        return float(value)

    except Exception:
        return default


def integer(
    value: Any,
    default=0,
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


def normalize_team(
    value: Any,
) -> str:
    team = clean_text(
        value
    ).upper()

    aliases = {
        "GS": "GSW",
        "NO": "NOP",
        "NY": "NYK",
        "SA": "SAS",
        "UTAH": "UTA",
        "WSH": "WAS",
    }

    return aliases.get(
        team,
        team,
    )


def dataframe_records(
    frame,
) -> list[dict[str, Any]]:
    if frame is None:
        return []

    try:
        frame = frame.where(
            frame.notna(),
            None,
        )

        return frame.to_dict(
            orient="records",
        )

    except Exception:
        return []


def save_json(
    payload: Any,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def publish(
    model_path: Path,
    web_path: Path,
) -> None:
    web_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    shutil.copy2(
        model_path,
        web_path,
    )


def attach_rankings_to_slates(
    payload: dict[str, Any],
) -> None:
    teams = payload.get(
        "teams",
        [],
    )

    lookup = {
        normalize_team(
            team.get("team")
        ): team
        for team in teams
        if isinstance(
            team,
            dict,
        )
        and team.get("team")
    }

    slate_files = [
        NBA_DIR
        / "slate.json",

        NBA_DIR
        / "next"
        / "slate.json",
    ]

    for slate_file in slate_files:
        if not slate_file.exists():
            continue

        try:
            slate_payload = json.loads(
                slate_file.read_text(
                    encoding="utf-8"
                )
            )

        except Exception as exc:
            print(
                f"   ⚠️ Could not read "
                f"{slate_file}: {exc}"
            )
            continue

        games = slate_payload.get(
            "games",
            [],
        )

        if not isinstance(
            games,
            list,
        ):
            continue

        attached = 0

        for game in games:
            if not isinstance(
                game,
                dict,
            ):
                continue

            away = normalize_team(
                game.get(
                    "away_team"
                )
            )

            home = normalize_team(
                game.get(
                    "home_team"
                )
            )

            away_data = (
                lookup.get(away)
            )

            home_data = (
                lookup.get(home)
            )

            if away_data:
                standings = (
                    away_data.get(
                        "standings",
                        {},
                    )
                )

                game[
                    "away_record"
                ] = standings.get(
                    "record",
                    "0-0",
                )

                game[
                    "away_nba_rank"
                ] = standings.get(
                    "nba_rank"
                )

                game[
                    "away_conference_rank"
                ] = standings.get(
                    "conference_rank"
                )

                game[
                    "away_division_rank"
                ] = standings.get(
                    "division_rank"
                )

            if home_data:
                standings = (
                    home_data.get(
                        "standings",
                        {},
                    )
                )

                game[
                    "home_record"
                ] = standings.get(
                    "record",
                    "0-0",
                )

                game[
                    "home_nba_rank"
                ] = standings.get(
                    "nba_rank"
                )

                game[
                    "home_conference_rank"
                ] = standings.get(
                    "conference_rank"
                )

                game[
                    "home_division_rank"
                ] = standings.get(
                    "division_rank"
                )

            if (
                away_data
                or home_data
            ):
                attached += 1

        save_json(
            slate_payload,
            slate_file,
        )

        relative = (
            slate_file.relative_to(
                NBA_DIR
            )
        )

        web_file = (
            WEB_NBA_DIR
            / relative
        )

        publish(
            slate_file,
            web_file,
        )

        print(
            f"   ✅ Rankings attached "
            f"to {attached} games: "
            f"{relative}"
        )


def build_nba_team_rankings():
    print()
    print(
        "🏆 BUILDING NBA TEAM RANKINGS"
    )
    print()

    response = (
        leaguestandings.LeagueStandings(
            season=CURRENT_SEASON,
            season_type="Regular Season",
            timeout=60,
        )
    )

    frame = (
        response.get_data_frames()[0]
    )

    rows = dataframe_records(
        frame
    )

    teams = []

    for row in rows:
        team = normalize_team(
            row.get(
                "TeamCity"
            )
        )

        team_name = clean_text(
            row.get(
                "TeamName"
            )
        )

        # LeagueStandings doesn't always
        # expose abbreviation directly.
        full_name = (
            f"{clean_text(row.get('TeamCity'))} "
            f"{team_name}"
        ).strip()

        full_name_to_abbr = {
            "Atlanta Hawks": "ATL",
            "Boston Celtics": "BOS",
            "Brooklyn Nets": "BKN",
            "Charlotte Hornets": "CHA",
            "Chicago Bulls": "CHI",
            "Cleveland Cavaliers": "CLE",
            "Dallas Mavericks": "DAL",
            "Denver Nuggets": "DEN",
            "Detroit Pistons": "DET",
            "Golden State Warriors": "GSW",
            "Houston Rockets": "HOU",
            "Indiana Pacers": "IND",
            "LA Clippers": "LAC",
            "Los Angeles Clippers": "LAC",
            "Los Angeles Lakers": "LAL",
            "Memphis Grizzlies": "MEM",
            "Miami Heat": "MIA",
            "Milwaukee Bucks": "MIL",
            "Minnesota Timberwolves": "MIN",
            "New Orleans Pelicans": "NOP",
            "New York Knicks": "NYK",
            "Oklahoma City Thunder": "OKC",
            "Orlando Magic": "ORL",
            "Philadelphia 76ers": "PHI",
            "Phoenix Suns": "PHX",
            "Portland Trail Blazers": "POR",
            "Sacramento Kings": "SAC",
            "San Antonio Spurs": "SAS",
            "Toronto Raptors": "TOR",
            "Utah Jazz": "UTA",
            "Washington Wizards": "WAS",
        }

        team = (
            full_name_to_abbr.get(
                full_name,
                team,
            )
        )

        wins = integer(
            row.get("WINS")
        )

        losses = integer(
            row.get("LOSSES")
        )

        record = clean_text(
            row.get("Record")
        )

        if not record:
            record = (
                f"{wins}-{losses}"
            )

        conference = clean_text(
            row.get(
                "Conference"
            )
        )

        division = clean_text(
            row.get(
                "Division"
            )
        )

        teams.append(
            {
                "team": team,
                "team_id": row.get(
                    "TeamID"
                ),
                "team_name": full_name,
                "conference": conference,
                "division": division,

                "standings": {
                    "record": record,
                    "wins": wins,
                    "losses": losses,

                    "win_pct": number(
                        row.get(
                            "WinPCT"
                        )
                    ),

                    "nba_rank": integer(
                        row.get(
                            "LeagueRank"
                        ),
                        None,
                    ),

                    "conference_rank": integer(
                        row.get(
                            "PlayoffRank"
                        ),
                        None,
                    ),

                    "division_rank": integer(
                        row.get(
                            "DivisionRank"
                        ),
                        None,
                    ),

                    "home_record": clean_text(
                        row.get(
                            "HOME"
                        )
                    ),

                    "road_record": clean_text(
                        row.get(
                            "ROAD"
                        )
                    ),

                    "last_10": clean_text(
                        row.get(
                            "L10"
                        )
                    ),

                    "conference_record": clean_text(
                        row.get(
                            "ConferenceGamesBack"
                        )
                    ),

                    "division_record": clean_text(
                        row.get(
                            "DivisionGamesBack"
                        )
                    ),

                    "points_per_game": number(
                        row.get(
                            "PointsPG"
                        )
                    ),

                    "opponent_points_per_game": number(
                        row.get(
                            "OppPointsPG"
                        )
                    ),

                    "point_differential": number(
                        row.get(
                            "DiffPointsPG"
                        )
                    ),
                },
            }
        )

    # LeagueRank is not guaranteed
    # to be useful before games begin.
    #
    # Once games exist, guarantee a
    # deterministic overall NBA rank
    # using record + point differential.

    teams.sort(
        key=lambda team: (
            -number(
                team[
                    "standings"
                ].get(
                    "win_pct"
                )
            ),
            -number(
                team[
                    "standings"
                ].get(
                    "point_differential"
                )
            ),
            team.get(
                "team",
                "",
            ),
        )
    )

    games_played = any(
        (
            team[
                "standings"
            ].get(
                "wins",
                0,
            )
            +
            team[
                "standings"
            ].get(
                "losses",
                0,
            )
        )
        > 0
        for team in teams
    )

    if games_played:
        for index, team in enumerate(
            teams,
            start=1,
        ):
            team[
                "standings"
            ][
                "nba_rank"
            ] = index

    else:
        # Preseason / before opening night:
        # standings are legitimately 0-0.
        for team in teams:
            team[
                "standings"
            ][
                "nba_rank"
            ] = None

            team[
                "standings"
            ][
                "conference_rank"
            ] = None

            team[
                "standings"
            ][
                "division_rank"
            ] = None

    payload = {
        "season": CURRENT_SEASON,
        "generated_at": (
            datetime.now(
                CENTRAL
            ).isoformat()
        ),
        "teams": teams,
    }

    save_json(
        payload,
        OUTPUT_FILE,
    )

    publish(
        OUTPUT_FILE,
        WEB_OUTPUT_FILE,
    )

    print(
        f"   ✅ {len(teams)} teams"
    )

    print(
        f"   model: {OUTPUT_FILE}"
    )

    print(
        f"   web:   {WEB_OUTPUT_FILE}"
    )

    attach_rankings_to_slates(
        payload
    )

    print()
    print(
        "✅ NBA TEAM RANKINGS COMPLETE"
    )

    return payload


if __name__ == "__main__":
    build_nba_team_rankings()