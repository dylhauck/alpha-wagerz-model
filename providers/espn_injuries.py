from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from utils.json_utils import save_json


MLB_TEAMS_URL = "https://statsapi.mlb.com/api/v1/teams"
MLB_TRANSACTIONS_URL = "https://statsapi.mlb.com/api/v1/transactions"
MLB_PEOPLE_URL = "https://statsapi.mlb.com/api/v1/people"

ESPN_ROSTER_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/"
    "teams/{team_slug}/roster"
)

ESPN_TEAMS = {
    "ari": "Arizona Diamondbacks",
    "atl": "Atlanta Braves",
    "bal": "Baltimore Orioles",
    "bos": "Boston Red Sox",
    "chc": "Chicago Cubs",
    "chw": "Chicago White Sox",
    "cin": "Cincinnati Reds",
    "cle": "Cleveland Guardians",
    "col": "Colorado Rockies",
    "det": "Detroit Tigers",
    "hou": "Houston Astros",
    "kc": "Kansas City Royals",
    "laa": "Los Angeles Angels",
    "lad": "Los Angeles Dodgers",
    "mia": "Miami Marlins",
    "mil": "Milwaukee Brewers",
    "min": "Minnesota Twins",
    "nym": "New York Mets",
    "nyy": "New York Yankees",
    "oak": "Athletics",
    "phi": "Philadelphia Phillies",
    "pit": "Pittsburgh Pirates",
    "sd": "San Diego Padres",
    "sf": "San Francisco Giants",
    "sea": "Seattle Mariners",
    "stl": "St. Louis Cardinals",
    "tb": "Tampa Bay Rays",
    "tex": "Texas Rangers",
    "tor": "Toronto Blue Jays",
    "wsh": "Washington Nationals",
}

OUTPUT_FILE = Path("data/processed/injury_report.json")

REQUEST_TIMEOUT = 30


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def get_json(
    url: str,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = requests.get(
        url,
        params=params or {},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def normalize_availability(
    description: str,
    type_desc: str = "",
) -> str:
    value = f"{description} {type_desc}".lower()

    if any(
        marker in value
        for marker in [
            "day-to-day",
            "day to day",
            "dtd",
        ]
    ):
        return "DTD"

    return "OUT"


def is_relevant_transaction(
    description: str,
    type_desc: str,
) -> bool:
    value = f"{description} {type_desc}".lower()

    return any(
        marker in value
        for marker in [
            "injured list",
            "disabled list",
            "day-to-day",
            "day to day",
            "suspend",
            "reinstated",
            "activated",
            "returned from",
        ]
    )


def is_activation(
    description: str,
    type_desc: str,
) -> bool:
    value = f"{description} {type_desc}".lower()

    return any(
        marker in value
        for marker in [
            "reinstated",
            "activated",
            "returned from",
        ]
    )


def is_suspension(
    description: str,
    type_desc: str,
) -> bool:
    return "suspend" in f"{description} {type_desc}".lower()


def parse_il_days(
    description: str,
) -> int | None:
    match = re.search(
        r"(\d+)-day (?:injured|disabled) list",
        description,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    return int(match.group(1))


# Replace ONLY your existing parse_injury() function with this version.

def parse_injury(
    description: str,
    type_desc: str = "",
) -> str:
    text = clean_text(description)
    combined = f"{text} {type_desc}".lower()

    if "suspend" in combined:
        return "Suspension"

    parenthetical = re.search(r"\(([^()]{2,120})\)", text)

    if parenthetical:
        injury = clean_text(parenthetical.group(1))

        if injury and not injury.isdigit():
            return injury

    sentence_parts = [
        clean_text(part)
        for part in re.split(r"[.;]", text)
        if clean_text(part)
    ]

    injury_keywords = [
        "surgery",
        "recovery",
        "strain",
        "sprain",
        "fracture",
        "inflammation",
        "soreness",
        "tightness",
        "tear",
        "elbow",
        "shoulder",
        "hamstring",
        "knee",
        "back",
        "wrist",
        "ankle",
        "hip",
        "groin",
        "forearm",
        "ucl",
        "labrum",
        "adductor",
        "oblique",
        "concussion",
    ]

    for part in reversed(sentence_parts):
        lowered = part.lower()

        if any(keyword in lowered for keyword in injury_keywords):
            return part

    patterns = [
        r"(?:with|due to|because of)\s+(?:a|an|the)?\s*([^.;]+)",
        r"(?:sidelined by|dealing with)\s+([^.;]+)",
        r"(?:recovering from)\s+([^.;]+)",
        r"(?:diagnosed with)\s+([^.;]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

        if match:
            injury = clean_text(match.group(1))

            if injury:
                return injury

    return "Undisclosed"



def parse_official_status(
    description: str,
    type_desc: str,
) -> str:
    value = f"{description} {type_desc}".lower()

    if "suspend" in value:
        return "Suspended"

    if any(
        marker in value
        for marker in [
            "day-to-day",
            "day to day",
            "dtd",
        ]
    ):
        return "Day-To-Day"

    il_days = parse_il_days(description)
    if il_days:
        return f"{il_days}-Day IL"

    if "injured list" in value or "disabled list" in value:
        return "Injured List"

    return clean_text(type_desc) or "OUT"


def format_date(
    value: date | None,
) -> str:
    if value is None:
        return "Unknown"

    return value.strftime("%b %-d, %Y")


def estimated_return_from_transaction(
    transaction: dict[str, Any],
    description: str,
    type_desc: str,
) -> str:
    if is_suspension(description, type_desc):
        resolution = transaction.get("resolutionDate")
        if resolution:
            try:
                parsed = datetime.strptime(
                    resolution,
                    "%Y-%m-%d",
                ).date()
                return f"Eligible {format_date(parsed)}"
            except ValueError:
                pass

        return "Unknown"

    il_days = parse_il_days(description)
    effective = (
        transaction.get("effectiveDate")
        or transaction.get("date")
    )

    if il_days and effective:
        try:
            start = datetime.strptime(
                effective,
                "%Y-%m-%d",
            ).date()

            eligible = start + timedelta(days=il_days)

            return f"Eligible {format_date(eligible)}"
        except ValueError:
            pass

    return "Unknown"


def fetch_mlb_teams() -> list[dict[str, Any]]:
    payload = get_json(
        MLB_TEAMS_URL,
        {
            "sportId": 1,
        },
    )

    return payload.get("teams", [])


def fetch_team_transactions(
    team_id: int,
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    payload = get_json(
        MLB_TRANSACTIONS_URL,
        {
            "teamId": team_id,
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
        },
    )

    return payload.get("transactions", [])


def fetch_positions(
    person_ids: list[int],
) -> dict[int, str]:
    if not person_ids:
        return {}

    positions: dict[int, str] = {}

    # Keep requests reasonably small.
    chunk_size = 100

    for start in range(0, len(person_ids), chunk_size):
        chunk = person_ids[start:start + chunk_size]

        payload = get_json(
            MLB_PEOPLE_URL,
            {
                "personIds": ",".join(str(person_id) for person_id in chunk),
                "hydrate": "currentTeam",
            },
        )

        for person in payload.get("people", []):
            person_id = person.get("id")
            position = person.get("primaryPosition") or {}

            abbreviation = (
                position.get("abbreviation")
                or position.get("code")
                or ""
            )

            if person_id:
                positions[int(person_id)] = clean_text(abbreviation)

    return positions


def build_current_status_rows() -> list[dict[str, Any]]:
    today = date.today()
    start_date = date(today.year, 1, 1)

    active: dict[tuple[int, int], dict[str, Any]] = {}

    teams = fetch_mlb_teams()

    for team in teams:
        team_id = team.get("id")
        team_name = clean_text(team.get("name"))

        if not team_id:
            continue

        transactions = fetch_team_transactions(
            int(team_id),
            start_date,
            today,
        )

        transactions = sorted(
            transactions,
            key=lambda item: (
                item.get("effectiveDate")
                or item.get("date")
                or "",
                item.get("id")
                or 0,
            ),
        )

        for transaction in transactions:
            description = clean_text(
                transaction.get("description")
            )
            type_desc = clean_text(
                transaction.get("typeDesc")
            )

            if not is_relevant_transaction(
                description,
                type_desc,
            ):
                continue

            person = transaction.get("person") or {}
            player_id = person.get("id")
            player_name = clean_text(
                person.get("fullName")
            )

            if not player_id or not player_name:
                continue

            key = (
                int(team_id),
                int(player_id),
            )

            if is_activation(
                description,
                type_desc,
            ):
                active.pop(key, None)
                continue

            active[key] = {
                "team": team_name,
                "player_id": int(player_id),
                "player": player_name,
                "position": "",
                "availability": normalize_availability(
                    description,
                    type_desc,
                ),
                "espn_status": parse_official_status(
                    description,
                    type_desc,
                ),
                "injury": parse_injury(
                    description,
                    type_desc,
                ),
                "estimated_return": estimated_return_from_transaction(
                    transaction,
                    description,
                    type_desc,
                ),
                "comment": description,
                "source": "MLB Transactions",
                "source_type": (
                    "suspension"
                    if is_suspension(
                        description,
                        type_desc,
                    )
                    else "injury"
                ),
                "transaction_date": (
                    transaction.get("effectiveDate")
                    or transaction.get("date")
                    or ""
                ),
            }

    person_ids = sorted(
        {
            row["player_id"]
            for row in active.values()
        }
    )

    positions = fetch_positions(person_ids)

    rows = list(active.values())

    for row in rows:
        row["position"] = positions.get(
            row["player_id"],
            "",
        )

    rows.sort(
        key=lambda row: (
            row.get("team", ""),
            0 if row.get("availability") == "OUT" else 1,
            row.get("player", ""),
        )
    )

    return rows



def normalized_name(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        clean_text(value).lower(),
    ).strip()


def iter_espn_athletes(payload: dict[str, Any]):
    for group in payload.get("athletes", []):
        if not isinstance(group, dict):
            continue

        group_position = clean_text(group.get("position"))

        for athlete in group.get("items", []):
            if not isinstance(athlete, dict):
                continue

            yield athlete, group_position


def value_text(value: Any) -> str:
    if isinstance(value, dict):
        preferred_keys = [
            "displayName",
            "name",
            "shortName",
            "description",
            "detail",
            "details",
            "shortComment",
            "longComment",
            "comment",
            "status",
            "type",
            "returnDate",
            "date",
        ]

        parts = [
            value_text(value.get(key))
            for key in preferred_keys
            if value.get(key) not in (None, "", [], {})
        ]

        if parts:
            return clean_text(" ".join(parts))

        return clean_text(
            " ".join(
                value_text(item)
                for item in value.values()
                if item not in (None, "", [], {})
            )
        )

    if isinstance(value, list):
        return clean_text(
            " ".join(
                value_text(item)
                for item in value
                if item not in (None, "", [], {})
            )
        )

    return clean_text(value)


def collect_espn_injury_text(athlete: dict[str, Any]) -> str:
    candidates: list[Any] = []

    for key, value in athlete.items():
        lowered = clean_text(key).lower()

        if any(
            marker in lowered
            for marker in [
                "injur",
                "status",
                "availability",
            ]
        ):
            candidates.append(value)

    return clean_text(" ".join(value_text(item) for item in candidates))


def is_espn_injury_status(text: str) -> bool:
    lowered = text.lower()

    healthy_markers = [
        "active",
        "healthy",
        "available",
        "no injury",
    ]

    injury_markers = [
        "day-to-day",
        "day to day",
        "dtd",
        "questionable",
        "doubtful",
        "out",
        "injured",
        "injury",
        "il",
        "disabled list",
        "soreness",
        "tightness",
        "strain",
        "sprain",
        "inflammation",
        "fracture",
        "concussion",
        "illness",
        "surgery",
    ]

    if any(marker in lowered for marker in injury_markers):
        return True

    if any(marker in lowered for marker in healthy_markers):
        return False

    return False


def espn_availability(text: str) -> str:
    lowered = text.lower()

    if any(
        marker in lowered
        for marker in [
            "day-to-day",
            "day to day",
            "dtd",
            "questionable",
        ]
    ):
        return "DTD"

    return "OUT"


def espn_status_label(text: str) -> str:
    lowered = text.lower()

    if any(
        marker in lowered
        for marker in [
            "day-to-day",
            "day to day",
            "dtd",
            "questionable",
        ]
    ):
        return "Day-To-Day"

    if "doubtful" in lowered:
        return "Doubtful"

    if "out" in lowered:
        return "Out"

    return "Injury"


def fetch_espn_roster_injuries() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json",
            "User-Agent": "Alpha-Wagerz/1.0",
        }
    )

    for team_slug, team_name in ESPN_TEAMS.items():
        url = ESPN_ROSTER_URL.format(team_slug=team_slug)

        try:
            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            errors.append(f"{team_slug}: {exc}")
            continue

        for athlete, group_position in iter_espn_athletes(payload):
            injury_text = collect_espn_injury_text(athlete)

            if not injury_text or not is_espn_injury_status(injury_text):
                continue

            position = athlete.get("position") or {}
            position_text = (
                clean_text(position.get("abbreviation"))
                if isinstance(position, dict)
                else clean_text(position)
            )

            if not position_text:
                position_text = group_position

            athlete_name = clean_text(
                athlete.get("fullName")
                or athlete.get("displayName")
            )

            if not athlete_name:
                continue

            availability = espn_availability(injury_text)

            rows.append(
                {
                    "team": team_name,
                    "player_id": None,
                    "espn_id": clean_text(athlete.get("id")),
                    "player": athlete_name,
                    "position": position_text,
                    "availability": availability,
                    "espn_status": espn_status_label(injury_text),
                    "injury": parse_injury(injury_text),
                    "estimated_return": "Unknown",
                    "comment": injury_text,
                    "source": "ESPN API",
                    "source_type": "injury",
                    "transaction_date": "",
                }
            )

    if not rows and errors:
        raise RuntimeError(
            "ESPN roster API returned no injury rows. "
            + " | ".join(errors[:5])
        )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}

    for row in rows:
        key = (
            normalized_name(row.get("team")),
            normalized_name(row.get("player")),
        )
        deduped[key] = row

    return list(deduped.values())


def merge_injury_rows(
    espn_rows: list[dict[str, Any]],
    mlb_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    # MLB Transactions stays authoritative for:
    # - official injured-list placements
    # - OUT statuses
    # - suspensions
    for row in mlb_rows:
        key = (
            normalized_name(row.get("team")),
            normalized_name(row.get("player")),
        )
        merged[key] = dict(row)

    # ESPN only supplements genuine day-to-day players.
    # It cannot overwrite an official MLB OUT or suspension record.
    for espn_row in espn_rows:
        if espn_row.get("availability") != "DTD":
            continue

        key = (
            normalized_name(espn_row.get("team")),
            normalized_name(espn_row.get("player")),
        )

        existing = merged.get(key)

        if existing and existing.get("source_type") == "suspension":
            continue

        if existing and existing.get("availability") == "OUT":
            continue

        combined = dict(existing or {})

        # Preserve MLB values if ESPN doesn't provide anything useful.
        for key, value in espn_row.items():
            if (
                key == "estimated_return"
                and (
                    value == "Unknown"
                    or value == ""
                    or value is None
                )
            ):
                continue

            if (
                key == "injury"
                and (
                    value == "Undisclosed"
                    or value == ""
                    or value is None
                )
            ):
                continue

            combined[key] = value


        if existing:
            combined["player_id"] = existing.get("player_id")
            combined["position"] = (
                espn_row.get("position")
                or existing.get("position")
                or ""
            )
            combined["transaction_date"] = existing.get(
                "transaction_date",
                "",
            )
            combined["source"] = "ESPN API + MLB Transactions"
        else:
            combined.setdefault("player_id", None)
            combined.setdefault("transaction_date", "")
            combined["source"] = "ESPN API"

        merged[key] = combined

    rows = list(merged.values())

    rows.sort(
        key=lambda row: (
            row.get("team", ""),
            0 if row.get("availability") == "DTD" else 1,
            row.get("player", ""),
        )
    )

    return rows


def build_injury_report():
    espn_rows: list[dict[str, Any]] = []
    espn_error = ""

    try:
        espn_rows = fetch_espn_roster_injuries()
        print(f"   ESPN API injuries: {len(espn_rows)}")
    except Exception as exc:
        espn_error = str(exc)
        print(f"⚠️ ESPN API injury pull failed: {exc}")

    mlb_rows = build_current_status_rows()
    print(f"   MLB transaction injuries/suspensions: {len(mlb_rows)}")

    players = merge_injury_rows(
        espn_rows,
        mlb_rows,
    )

    dtd_count = sum(
        1
        for player in players
        if player.get("availability") == "DTD"
    )
    out_count = sum(
        1
        for player in players
        if player.get("availability") == "OUT"
    )

    payload = {
        "generated_at": datetime.now()
        .astimezone()
        .isoformat(timespec="seconds"),
        "primary_source": (
            "ESPN API + MLB Transactions"
            if espn_rows
            else "MLB Transactions"
        ),
        "espn_available": bool(espn_rows),
        "espn_error": espn_error,
        "player_count": len(players),
        "dtd_count": dtd_count,
        "out_count": out_count,
        "players": players,
        "notes": (
            "Day-to-day statuses are read from ESPN's structured roster API. "
            "Official injured-list and suspension records are supplemented "
            "from MLB Transactions."
        ),
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_json(
        payload,
        OUTPUT_FILE,
    )

    print(
        f"✅ Saved injury report for {len(players)} players "
        f"({dtd_count} DTD, {out_count} OUT)"
    )
    print(f"📁 {OUTPUT_FILE}")

    return payload


if __name__ == "__main__":
    build_injury_report()