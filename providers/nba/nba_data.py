from __future__ import annotations

import json
import shutil
import time

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from requests.exceptions import RequestException

from nba_api.stats.endpoints import scheduleleaguev2


# ============================================================
# PATHS / CONFIG
# ============================================================

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

SCHEDULE_FILE = NBA_DIR / "schedule.json"
SLATE_FILE = NBA_DIR / "slate.json"
NEXT_SLATE_FILE = (
    NBA_DIR
    / "next"
    / "slate.json"
)

WEB_SCHEDULE_FILE = (
    WEB_NBA_DIR
    / "schedule.json"
)

WEB_SLATE_FILE = (
    WEB_NBA_DIR
    / "slate.json"
)

WEB_NEXT_SLATE_FILE = (
    WEB_NBA_DIR
    / "next"
    / "slate.json"
)

CURRENT_SEASON = "2026-27"

CENTRAL = ZoneInfo(
    "America/Chicago"
)

# The 2026-27 NBA regular season begins
# Tuesday, October 20, 2026.
REGULAR_SEASON_START = datetime(
    2026,
    10,
    20,
).date()


# ============================================================
# HELPERS
# ============================================================

def clean_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def safe_int(
    value: Any,
) -> int | None:
    if value is None:
        return None

    try:
        return int(float(value))
    except (
        TypeError,
        ValueError,
    ):
        return None


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


def dataframe_records(
    frame: Any,
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


def parse_nba_datetime(
    value: Any,
) -> str | None:
    text = clean_text(value)

    if not text:
        return None

    # Preserve the NBA API ISO datetime.
    return text


def parse_game_date(
    row: dict[str, Any],
) -> str:
    """
    Prefer the NBA's Eastern game date because
    schedule days are conventionally grouped
    by the local NBA schedule date.
    """

    candidates = [
        row.get("gameDate"),
        row.get("gameDateEst"),
    ]

    for value in candidates:
        text = clean_text(value)

        if not text:
            continue

        # Normal YYYY-MM-DD
        try:
            return datetime.strptime(
                text[:10],
                "%Y-%m-%d",
            ).date().isoformat()
        except ValueError:
            pass

        # Example:
        # 10/20/2026 12:00:00 AM
        for fmt in (
            "%m/%d/%Y",
            "%m/%d/%Y %I:%M:%S %p",
        ):
            try:
                return datetime.strptime(
                    text,
                    fmt,
                ).date().isoformat()
            except ValueError:
                continue

    return ""


def record_text(
    wins: Any,
    losses: Any,
) -> str:
    wins_int = safe_int(wins)
    losses_int = safe_int(losses)

    if wins_int is None:
        wins_int = 0

    if losses_int is None:
        losses_int = 0

    return (
        f"{wins_int}-{losses_int}"
    )


# ============================================================
# SCHEDULE
# ============================================================

def load_existing_schedule() -> list[dict[str, Any]]:
    if not SCHEDULE_FILE.exists():
        raise FileNotFoundError(
            f"NBA schedule fallback not found: {SCHEDULE_FILE}"
        )

    payload = json.loads(
        SCHEDULE_FILE.read_text(
            encoding="utf-8"
        )
    )

    games = payload.get("games")

    if not isinstance(games, list) or not games:
        raise ValueError(
            f"NBA schedule fallback is invalid: {SCHEDULE_FILE}"
        )

    print(
        f"   Using existing NBA schedule fallback: "
        f"{len(games)} games"
    )

    return games

def build_schedule() -> list[dict[str, Any]]:
    print()
    print(
        "🏀 Loading 2026-27 NBA schedule..."
    )

    max_attempts = 3
    response = None

    for attempt in range(1, max_attempts + 1):
        try:
            print(
                f"   NBA schedule request "
                f"(attempt {attempt}/{max_attempts})..."
            )

            response = (
                scheduleleaguev2.ScheduleLeagueV2(
                    league_id="00",
                    season=CURRENT_SEASON,
                    timeout=90,
                )
            )

            print(
                "   NBA schedule request successful."
            )
            break

        except RequestException as exc:
            print(
                f"   NBA schedule request failed: "
                f"on attempt {attempt}: "
                f"{type(exc).__name__}: {exc}"
            )

            if attempt < max_attempts:
                wait_seconds = attempt * 10

            print(
                f"   Waiting {wait_seconds} seconds "
                f"before retrying..."
            )

            time.sleep(wait_seconds)


    if response is None:
        print(
            "   NBA Stats API unavailable after "
            f"{max_attempts} attempts."
        )
        return load_existing_schedule()

    # ScheduleLeagueV2 exposes the actual
    # season schedule as SeasonGames.
    frame = (
        response.season_games
        .get_data_frame()
    )

    rows = dataframe_records(
        frame
    )

    print(
        f"   Raw NBA schedule rows: "
        f"{len(rows)}"
    )

    games: list[
        dict[str, Any]
    ] = []

    skipped_preseason = 0
    skipped_invalid = 0

    for row in rows:
        game_id = clean_text(
            row.get("gameId")
        )

        away_team = clean_text(
            row.get(
                "awayTeam_teamTricode"
            )
        ).upper()

        home_team = clean_text(
            row.get(
                "homeTeam_teamTricode"
            )
        ).upper()

        game_date = parse_game_date(
            row
        )

        if (
            not game_id
            or not away_team
            or not home_team
            or not game_date
        ):
            skipped_invalid += 1
            continue

        try:
            game_date_obj = (
                datetime.strptime(
                    game_date,
                    "%Y-%m-%d",
                ).date()
            )
        except ValueError:
            skipped_invalid += 1
            continue

        # ScheduleLeagueV2 can include preseason
        # games for the season. Alpha Wagerz NBA
        # slate is regular season, so remove all
        # games before opening night.
        if (
            game_date_obj
            < REGULAR_SEASON_START
        ):
            skipped_preseason += 1
            continue

        game_status_code = safe_int(
            row.get("gameStatus")
        )

        game_status_text = clean_text(
            row.get(
                "gameStatusText"
            )
        )

        if not game_status_text:
            if game_status_code == 3:
                game_status_text = "Final"
            elif game_status_code == 2:
                game_status_text = (
                    "In Progress"
                )
            else:
                game_status_text = (
                    "Scheduled"
                )

        away_score = safe_int(
            row.get(
                "awayTeam_score"
            )
        )

        home_score = safe_int(
            row.get(
                "homeTeam_score"
            )
        )

        # Scheduled games frequently expose zero
        # as the score. Do not treat that as a
        # completed 0-0 game.
        if game_status_code != 3:
            away_score = None
            home_score = None

        arena = clean_text(
            row.get("arenaName")
        ) or None

        arena_city = clean_text(
            row.get("arenaCity")
        ) or None

        arena_state = clean_text(
            row.get("arenaState")
        ) or None

        game_datetime = (
            parse_nba_datetime(
                row.get(
                    "gameDateTimeEst"
                )
            )
        )

        game_datetime_utc = (
            parse_nba_datetime(
                row.get(
                    "gameDateTimeUTC"
                )
            )
        )

        game_time = clean_text(
            row.get("gameTimeEst")
        ) or None

        away_wins = row.get(
            "awayTeam_wins"
        )

        away_losses = row.get(
            "awayTeam_losses"
        )

        home_wins = row.get(
            "homeTeam_wins"
        )

        home_losses = row.get(
            "homeTeam_losses"
        )

        game = {
            "game_id": game_id,

            "season": CURRENT_SEASON,
            "game_type": "REG",

            "game_date": game_date,
            "game_time": game_time,

            "game_datetime": (
                game_datetime
            ),

            "game_datetime_utc": (
                game_datetime_utc
            ),

            "away_team": away_team,
            "home_team": home_team,

            "away_abbr": away_team,
            "home_abbr": home_team,

            "away_record": record_text(
                away_wins,
                away_losses,
            ),

            "home_record": record_text(
                home_wins,
                home_losses,
            ),

            "venue": arena,
            "arena": arena,

            "arena_city": arena_city,
            "arena_state": arena_state,

            "status": (
                game_status_text
            ),

            "status_code": (
                game_status_code
            ),

            "away_score": away_score,
            "home_score": home_score,

            "week_number": safe_int(
                row.get(
                    "weekNumber"
                )
            ),

            "week_name": clean_text(
                row.get(
                    "weekName"
                )
            ) or None,

            "game_label": clean_text(
                row.get(
                    "gameLabel"
                )
            ) or None,

            "game_sub_label": clean_text(
                row.get(
                    "gameSubLabel"
                )
            ) or None,

            "game_subtype": clean_text(
                row.get(
                    "gameSubtype"
                )
            ) or None,

            "is_neutral": row.get(
                "isNeutral"
            ),
        }

        games.append(
            game
        )

    games.sort(
        key=lambda game: (
            game.get(
                "game_date"
            )
            or "",
            game.get(
                "game_datetime_utc"
            )
            or "",
            game.get(
                "game_id"
            )
            or "",
        )
    )

    print(
        f"   Preseason rows skipped: "
        f"{skipped_preseason}"
    )

    if skipped_invalid:
        print(
            f"   Invalid rows skipped: "
            f"{skipped_invalid}"
        )

    print(
        f"   ✅ {len(games)} "
        f"regular-season games"
    )

    if games:
        print(
            f"   First game date: "
            f"{games[0]['game_date']}"
        )

        print(
            f"   Last game date:  "
            f"{games[-1]['game_date']}"
        )

    return games


# ============================================================
# CURRENT / FUTURE SLATES
# ============================================================

def find_current_and_next_slate(
    games: list[dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    Current Slate:
        Next available NBA game date on or
        after today.

    Future Slate:
        Following NBA game date.

    Empty calendar dates are skipped.
    """

    today = datetime.now(
        CENTRAL
    ).date()

    games_by_date: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    for game in games:
        raw_date = clean_text(
            game.get("game_date")
        )

        if not raw_date:
            continue

        try:
            game_date = (
                datetime.strptime(
                    raw_date,
                    "%Y-%m-%d",
                ).date()
            )
        except ValueError:
            continue

        if game_date < today:
            continue

        games_by_date.setdefault(
            game_date.isoformat(),
            [],
        ).append(
            game
        )

    available_dates = sorted(
        games_by_date.keys()
    )

    if not available_dates:
        print()
        print(
            "   ⚠️ No future NBA "
            "regular-season games found."
        )

        return [], []

    current_date = (
        available_dates[0]
    )

    future_date = (
        available_dates[1]
        if len(available_dates) > 1
        else None
    )

    current_games = (
        games_by_date[
            current_date
        ]
    )

    future_games = (
        games_by_date[
            future_date
        ]
        if future_date
        else []
    )

    print()
    print(
        f"   Current NBA slate: "
        f"{current_date} "
        f"({len(current_games)} games)"
    )

    if future_date:
        print(
            f"   Future NBA slate:  "
            f"{future_date} "
            f"({len(future_games)} games)"
        )
    else:
        print(
            "   Future NBA slate:  none"
        )

    return (
        current_games,
        future_games,
    )


# ============================================================
# BUILD
# ============================================================

def build_nba_data() -> None:
    print()
    print(
        "🏀 BUILDING NBA DATA"
    )
    print()

    NBA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    WEB_NBA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    games = build_schedule()

    (
        current_games,
        future_games,
    ) = find_current_and_next_slate(
        games
    )

    generated_at = (
        datetime.now(
            CENTRAL
        ).isoformat()
    )

    schedule_payload = {
        "season": CURRENT_SEASON,
        "generated_at": generated_at,
        "games": games,
    }

    slate_payload = {
        "season": CURRENT_SEASON,
        "generated_at": generated_at,
        "slate_type": "current",
        "slate_date": (
            current_games[0][
                "game_date"
            ]
            if current_games
            else None
        ),
        "games": current_games,
    }

    future_payload = {
        "season": CURRENT_SEASON,
        "generated_at": generated_at,
        "slate_type": "future",
        "slate_date": (
            future_games[0][
                "game_date"
            ]
            if future_games
            else None
        ),
        "games": future_games,
    }

    save_json(
        schedule_payload,
        SCHEDULE_FILE,
    )

    save_json(
        slate_payload,
        SLATE_FILE,
    )

    save_json(
        future_payload,
        NEXT_SLATE_FILE,
    )

    publish(
        SCHEDULE_FILE,
        WEB_SCHEDULE_FILE,
    )

    publish(
        SLATE_FILE,
        WEB_SLATE_FILE,
    )

    publish(
        NEXT_SLATE_FILE,
        WEB_NEXT_SLATE_FILE,
    )

    print()
    print(
        "✅ schedule.json"
    )
    print(
        f"   model: "
        f"{SCHEDULE_FILE}"
    )
    print(
        f"   web:   "
        f"{WEB_SCHEDULE_FILE}"
    )

    print()
    print(
        "✅ Current slate.json"
    )

    if current_games:
        print(
            f"   date:  "
            f"{current_games[0]['game_date']}"
        )

    print(
        f"   games: "
        f"{len(current_games)}"
    )

    print()
    print(
        "✅ Future next/slate.json"
    )

    if future_games:
        print(
            f"   date:  "
            f"{future_games[0]['game_date']}"
        )

    print(
        f"   games: "
        f"{len(future_games)}"
    )

    print()
    print(
        "✅ NBA DATA BUILD COMPLETE"
    )


if __name__ == "__main__":
    build_nba_data()

