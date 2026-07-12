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


def build_injury_report():
    players = build_current_status_rows()

    payload = {
        "generated_at": datetime.now()
        .astimezone()
        .isoformat(timespec="seconds"),
        "primary_source": "MLB Transactions",
        "espn_available": False,
        "espn_error": "",
        "player_count": len(players),
        "players": players,
        "notes": (
            "Estimated return values are official eligibility dates derived "
            "from IL placement length when MLB provides enough information."
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
        f"✅ Saved MLB injury report for "
        f"{len(players)} players"
    )
    print(f"📁 {OUTPUT_FILE}")

    return payload


if __name__ == "__main__":
    build_injury_report()
