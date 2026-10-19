from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATA = ROOT / "data" / "processed" / "nba"

WEB = (
    ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nba"
)

OUT = DATA / "injuries.json"
WEB_OUT = WEB / "injuries.json"

SLATE = DATA / "slate.json"

ESPN_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/injuries"
)

TIMEOUT = 45
MAX_ATTEMPTS = 3

TEAM_ALIASES = {
    "GS": "GSW",
    "GSW": "GSW",
    "NY": "NYK",
    "NYK": "NYK",
    "SA": "SAS",
    "SAS": "SAS",
    "NO": "NOP",
    "NOLA": "NOP",
    "NOP": "NOP",
    "UTAH": "UTA",
    "UTA": "UTA",
    "PHO": "PHX",
    "PHX": "PHX",
    "BKN": "BKN",
    "BRK": "BKN",
    "CHA": "CHA",
    "CHO": "CHA",
}


# ============================================================
# HELPERS
# ============================================================

def save_json(path: Path, payload: Any):
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


def clean(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def normalize_team(value: Any) -> str:
    team = clean(value).upper()

    return TEAM_ALIASES.get(
        team,
        team,
    )


def get_text(value: Any) -> str:
    if isinstance(value, dict):
        return clean(
            value.get("displayName")
            or value.get("name")
            or value.get("description")
            or value.get("abbreviation")
            or value.get("shortName")
        )

    return clean(value)


def get_team_code(value: Any) -> str:
    if isinstance(value, dict):
        return normalize_team(
            value.get("abbreviation")
            or value.get("teamAbbreviation")
            or value.get("code")
        )

    return normalize_team(value)


def normalize_status(value: Any) -> str:
    status = get_text(value).upper()

    aliases = {
        "O": "OUT",
        "Q": "QUESTIONABLE",
        "D": "DOUBTFUL",
        "P": "PROBABLE",
        "DAY-TO-DAY": "DAY-TO-DAY",
    }

    return aliases.get(
        status,
        status or "UNKNOWN",
    )


# ============================================================
# ESPN REQUEST
# ============================================================

def fetch_injuries() -> dict:
    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; AlphaWagerz/1.0)"
            ),
            "Accept": "application/json",
        }
    )

    last_error = None

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):
        try:
            print(
                f"Fetching ESPN NBA injuries "
                f"({attempt}/{MAX_ATTEMPTS})...",
                flush=True,
            )

            response = session.get(
                ESPN_URL,
                timeout=TIMEOUT,
            )

            response.raise_for_status()

            payload = response.json()

            if not isinstance(payload, dict):
                raise ValueError(
                    "ESPN returned an invalid JSON structure."
                )

            if not isinstance(
                payload.get("injuries"),
                list,
            ):
                raise ValueError(
                    "ESPN response missing injuries array."
                )

            return payload

        except (
            requests.RequestException,
            ValueError,
        ) as exc:
            last_error = exc

            print(
                f"NBA injury request failed: {exc}",
                flush=True,
            )

            if attempt < MAX_ATTEMPTS:
                time.sleep(attempt * 3)

    raise RuntimeError(
        "Unable to retrieve valid NBA injury data "
        f"from ESPN: {last_error}"
    )


# ============================================================
# PARSE INJURY RECORD
# ============================================================

def parse_injury(
    entry: dict,
    fallback_team: str = "",
) -> dict | None:
    if not isinstance(entry, dict):
        return None

    athlete = entry.get("athlete") or {}

    if not isinstance(athlete, dict):
        athlete = {}

    injury = entry.get("injury") or {}

    if not isinstance(injury, dict):
        injury = {}

    team = get_team_code(
        entry.get("team")
    ) or fallback_team

    player_name = clean(
        athlete.get("displayName")
        or athlete.get("fullName")
        or entry.get("displayName")
        or entry.get("playerName")
    )

    if not team or not player_name:
        return None

    position = get_text(
        athlete.get("position")
        or entry.get("position")
    )

    status = normalize_status(
        injury.get("status")
        or entry.get("status")
    )

    injury_type = get_text(
        injury.get("type")
        or entry.get("type")
    )

    injury_side = get_text(
        injury.get("side")
        or entry.get("side")
    )

    details = injury.get("details") or {}

    if not isinstance(details, dict):
        details = {}

    detail = clean(
        details.get("longComment")
        or details.get("shortComment")
        or injury.get("description")
        or entry.get("description")
    )

    return_date = clean(
        details.get("returnDate")
        or details.get("returnAt")
        or injury.get("returnDate")
        or entry.get("returnDate")
    )

    reported_date = clean(
        injury.get("date")
        or entry.get("date")
    )

    injury_description = " ".join(
        part
        for part in [
            injury_side,
            injury_type,
        ]
        if part
    )

    return {
        "player_id": clean(
            athlete.get("id")
            or entry.get("id")
        ),
        "player_name": player_name,
        "team": team,
        "position": position,
        "status": status,
        "injury": (
            injury_description
            or injury_type
            or "Undisclosed"
        ),
        "detail": detail,
        "estimated_return_date": return_date,
        "reported_date": reported_date,
        "source": "ESPN",
    }


# ============================================================
# FLATTEN ESPN RESPONSE
# ============================================================

def extract_injuries(payload: dict) -> list[dict]:
    groups = payload.get("injuries", [])

    rows = []
    seen = set()

    for group in groups:
        if not isinstance(group, dict):
            continue

        group_team = get_team_code(
            group.get("team")
        )

        # ESPN commonly groups injuries by team.
        entries = group.get("injuries")

        if not isinstance(entries, list):
            entries = [group]

        for entry in entries:
            row = parse_injury(
                entry,
                fallback_team=group_team,
            )

            if row is None:
                continue

            key = (
                row["team"],
                row["player_id"] or row["player_name"],
                row["status"],
                row["injury"],
            )

            if key in seen:
                continue

            seen.add(key)
            rows.append(row)

    return sorted(
        rows,
        key=lambda row: (
            row["team"],
            row["player_name"],
        ),
    )


# ============================================================
# LOAD CURRENT SLATE
# ============================================================

def load_slate() -> dict:
    if not SLATE.exists():
        return {
            "slate_date": None,
            "games": [],
        }

    try:
        payload = json.loads(
            SLATE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(payload, list):
            return {
                "slate_date": None,
                "games": payload,
            }

        if isinstance(payload, dict):
            return payload

    except (
        OSError,
        ValueError,
    ):
        pass

    return {
        "slate_date": None,
        "games": [],
    }


# ============================================================
# MAIN BUILDER
# ============================================================

def build_nba_injuries():
    print(
        "\n🏥 Building NBA injury report...",
        flush=True,
    )

    payload = fetch_injuries()

    injuries = extract_injuries(payload)

    slate = load_slate()

    games = slate.get("games", [])

    if not isinstance(games, list):
        games = []

    slate_teams = set()

    for game in games:
        if not isinstance(game, dict):
            continue

        away = normalize_team(
            game.get("away_abbr")
            or game.get("away_team")
        )

        home = normalize_team(
            game.get("home_abbr")
            or game.get("home_team")
        )

        if away:
            slate_teams.add(away)

        if home:
            slate_teams.add(home)

    slate_injuries = [
        row
        for row in injuries
        if row["team"] in slate_teams
    ]

    output = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "source": "ESPN",
        "slate_date": slate.get("slate_date"),
        "status": "ok",
        "injury_count": len(injuries),
        "slate_injury_count": len(slate_injuries),
        "games": games,
        "injuries": injuries,
    }

    save_json(
        OUT,
        output,
    )

    save_json(
        WEB_OUT,
        output,
    )

    print(
        f"NBA injuries loaded: {len(injuries)}",
        flush=True,
    )

    print(
        f"Current slate injuries: "
        f"{len(slate_injuries)}",
        flush=True,
    )

    print(
        f"Saved: {OUT}",
        flush=True,
    )

    print(
        f"Saved web copy: {WEB_OUT}",
        flush=True,
    )

    return output


if __name__ == "__main__":
    build_nba_injuries()