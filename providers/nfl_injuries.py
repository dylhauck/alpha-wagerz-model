from __future__ import annotations

import json
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import certifi


MODEL_ROOT = Path(__file__).resolve().parents[1]
NFL_DIR = MODEL_ROOT / "data" / "processed" / "nfl"
WEB_NFL_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nfl"
)

OUTPUT_FILE = NFL_DIR / "injuries.json"
WEB_OUTPUT_FILE = WEB_NFL_DIR / "injuries.json"
ROSTERS_FILE = NFL_DIR / "rosters.json"

CURRENT_SEASON = 2026

ESPN_TEAMS_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/football/nfl/teams"
)

ESPN_LEAGUE_INJURIES_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/football/nfl/injuries"
)

ESPN_TEAM_INJURIES_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/football/nfl/teams/{team_id}/injuries"
)

REQUEST_TIMEOUT = 6
MAX_WORKERS = 8

TEAM_ALIASES = {
    "LA": "LAR",
    "JAC": "JAX",
    "WSH": "WAS",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def first_nonempty(*values: Any) -> str:
    for value in values:
        text = clean(value)
        if text:
            return text
    return ""


def normalize_team(value: Any) -> str:
    team = clean(value).upper()
    return TEAM_ALIASES.get(team, team)


def normalize_status(value: Any) -> str:
    status = clean(value).upper()

    aliases = {
        "Q": "QUESTIONABLE",
        "QUES": "QUESTIONABLE",
        "QUESTIONABLE": "QUESTIONABLE",
        "D": "DOUBTFUL",
        "DOUBTFUL": "DOUBTFUL",
        "O": "OUT",
        "OUT": "OUT",

        "IR": "IR",
        "INJURED RESERVE": "IR",
        "INJURED-RESERVE": "IR",
        "RESERVE/INJURED": "IR",
        "RESERVE-INJURED": "IR",

        "PUP": "PUP",
        "PHYSICALLY UNABLE TO PERFORM": "PUP",
        "RESERVE/PUP": "PUP",

        "NFI": "NFI",
        "NON-FOOTBALL INJURY": "NFI",
        "NON FOOTBALL INJURY": "NFI",
        "RESERVE/NFI": "NFI",

        "PROBABLE": "PROBABLE",
        "ACTIVE": "ACTIVE",
    }

    return aliases.get(status, status)


def normalize_practice_status(value: Any) -> str:
    status = clean(value).upper()

    aliases = {
        "DNP": "DNP",
        "DID NOT PARTICIPATE": "DNP",
        "LIMITED": "LIMITED",
        "LIMITED PARTICIPATION": "LIMITED",
        "LP": "LIMITED",
        "FULL": "FULL",
        "FULL PARTICIPATION": "FULL",
        "FP": "FULL",
    }

    return aliases.get(status, status)


def save_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            ensure_ascii=False,
        )


def load_json(path: Path, default: Any):
    if not path.exists():
        return default

    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def fetch_json(url: str) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Mozilla/5.0 Alpha-Wagerz-NFL-Injuries/1.0"
            ),
        },
    )

    ssl_context = ssl.create_default_context(
        cafile=certifi.where()
    )

    with urlopen(
        request,
        timeout=REQUEST_TIMEOUT,
        context=ssl_context,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def parse_espn_teams(
    payload: dict[str, Any],
) -> list[dict[str, str]]:
    teams: list[dict[str, str]] = []

    for sport in payload.get("sports", []):
        if not isinstance(sport, dict):
            continue

        for league in sport.get("leagues", []):
            if not isinstance(league, dict):
                continue

            for entry in league.get("teams", []):
                if not isinstance(entry, dict):
                    continue

                team = entry.get("team", entry)

                if not isinstance(team, dict):
                    continue

                team_id = clean(team.get("id"))
                abbr = normalize_team(
                    first_nonempty(
                        team.get("abbreviation"),
                        team.get("shortDisplayName"),
                    )
                )

                if team_id and abbr:
                    teams.append(
                        {
                            "id": team_id,
                            "abbr": abbr,
                        }
                    )

    return teams


def extract_status(raw: dict[str, Any]) -> str:
    status = raw.get("status")

    if isinstance(status, dict):
        status = first_nonempty(
            status.get("name"),
            status.get("description"),
            status.get("abbreviation"),
            status.get("type"),
        )

    return normalize_status(status)


def extract_practice_status(
    raw: dict[str, Any],
) -> str:
    value = (
        raw.get("practiceStatus")
        or raw.get("practice_status")
    )

    if isinstance(value, dict):
        value = first_nonempty(
            value.get("name"),
            value.get("description"),
            value.get("abbreviation"),
        )

    return normalize_practice_status(value)


def extract_injury_description(
    raw: dict[str, Any],
) -> str:
    details = raw.get("details")
    detail_text = ""

    if isinstance(details, dict):
        detail_text = first_nonempty(
            details.get("detail"),
            details.get("type"),
            details.get("location"),
            details.get("side"),
        )

    return first_nonempty(
        raw.get("shortComment"),
        raw.get("longComment"),
        raw.get("description"),
        raw.get("injury"),
        raw.get("type"),
        detail_text,
    )


def normalize_espn_row(
    team_abbr: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    athlete = raw.get("athlete")

    if not isinstance(athlete, dict):
        athlete = {}

    position = athlete.get("position")

    if not isinstance(position, dict):
        position = {}

    player_id = first_nonempty(
        athlete.get("id"),
        raw.get("athleteId"),
        raw.get("playerId"),
        raw.get("player_id"),
    )

    player = first_nonempty(
        athlete.get("fullName"),
        athlete.get("displayName"),
        athlete.get("shortName"),
        raw.get("player"),
        raw.get("player_name"),
        raw.get("name"),
    )

    pos = first_nonempty(
        position.get("abbreviation"),
        position.get("name"),
        raw.get("position"),
        raw.get("pos"),
    ).upper()

    status = extract_status(raw)
    practice_status = extract_practice_status(raw)
    injury = extract_injury_description(raw)

    if not status and injury:
        status = "INJURY"

    return {
        "player_id": player_id,
        "espn_id": player_id,
        "player": player,
        "team": normalize_team(team_abbr),
        "position": pos,
        "status": status,
        "practice_status": practice_status,
        "injury": injury,
        "source": "ESPN",
        "source_updated": first_nonempty(
            raw.get("date"),
            raw.get("lastUpdated"),
            raw.get("updated"),
        ),
    }


def injury_like_dict(node: dict[str, Any]) -> bool:
    athlete = node.get("athlete")

    if isinstance(athlete, dict):
        if first_nonempty(
            athlete.get("fullName"),
            athlete.get("displayName"),
            athlete.get("shortName"),
            athlete.get("id"),
        ):
            return True

    return bool(
        first_nonempty(
            node.get("player"),
            node.get("player_name"),
        )
        and any(
            key in node
            for key in (
                "status",
                "practiceStatus",
                "practice_status",
                "injury",
                "details",
                "description",
                "shortComment",
                "longComment",
            )
        )
    )


def collect_injury_dicts(
    node: Any,
) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    if isinstance(node, dict):
        if injury_like_dict(node):
            found.append(node)

        for value in node.values():
            if isinstance(value, (dict, list)):
                found.extend(
                    collect_injury_dicts(value)
                )

    elif isinstance(node, list):
        for value in node:
            found.extend(
                collect_injury_dicts(value)
            )

    return found


def parse_league_injuries(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    groups = payload.get("injuries", [])

    if not isinstance(groups, list):
        return rows

    for group in groups:
        if not isinstance(group, dict):
            continue

        team = group.get("team")

        if not isinstance(team, dict):
            team = {}

        team_abbr = normalize_team(
            first_nonempty(
                team.get("abbreviation"),
                group.get("teamAbbreviation"),
                group.get("team_abbr"),
            )
        )

        if not team_abbr:
            continue

        injuries = group.get("injuries", [])

        if not isinstance(injuries, list):
            injuries = collect_injury_dicts(group)

        for raw in injuries:
            if not isinstance(raw, dict):
                continue

            row = normalize_espn_row(
                team_abbr,
                raw,
            )

            if row["player"]:
                rows.append(row)

    return rows


def fetch_one_team(
    team: dict[str, str],
) -> tuple[list[dict[str, Any]], str]:
    url = ESPN_TEAM_INJURIES_URL.format(
        team_id=team["id"]
    )

    try:
        payload = fetch_json(url)

        raw_rows = collect_injury_dicts(payload)

        rows: list[dict[str, Any]] = []

        for raw in raw_rows:
            row = normalize_espn_row(
                team["abbr"],
                raw,
            )

            if not row["player"]:
                continue

            if not (
                row["status"]
                or row["practice_status"]
                or row["injury"]
            ):
                continue

            rows.append(row)

        return rows, ""

    except Exception as exc:
        return [], f'{team["abbr"]}: {exc}'


def fetch_team_injuries_fast(
    teams: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:
        futures = {
            executor.submit(
                fetch_one_team,
                team,
            ): team
            for team in teams
        }

        for future in as_completed(futures):
            team = futures[future]

            try:
                team_rows, error = future.result()
            except Exception as exc:
                team_rows = []
                error = (
                    f'{team["abbr"]}: {exc}'
                )

            rows.extend(team_rows)

            if error:
                errors.append(error)

    return rows, errors


def roster_injury_status(value: Any) -> str:
    raw = clean(value).upper()

    if not raw:
        return ""

    normalized = normalize_status(raw)

    if normalized in {
        "IR",
        "PUP",
        "NFI",
        "OUT",
        "DOUBTFUL",
        "QUESTIONABLE",
    }:
        return normalized

    if (
        "INJURED RESERVE" in raw
        or "RESERVE/INJURED" in raw
        or "RESERVE-INJURED" in raw
    ):
        return "IR"

    if (
        "PUP" in raw
        or "PHYSICALLY UNABLE" in raw
    ):
        return "PUP"

    if (
        "NFI" in raw
        or "NON-FOOTBALL INJURY" in raw
        or "NON FOOTBALL INJURY" in raw
    ):
        return "NFI"

    return ""


def extract_roster_rows(
    payload: Any,
) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [
            row
            for row in payload
            if isinstance(row, dict)
        ]

    if isinstance(payload, dict):
        for key in (
            "players",
            "rosters",
            "roster",
            "data",
        ):
            value = payload.get(key)

            if isinstance(value, list):
                return [
                    row
                    for row in value
                    if isinstance(row, dict)
                ]

    return []


def build_roster_reserve_injuries() -> list[dict[str, Any]]:
    rows = extract_roster_rows(
        load_json(
            ROSTERS_FILE,
            default=[],
        )
    )

    results: list[dict[str, Any]] = []

    for row in rows:
        raw_status = first_nonempty(
            row.get("status"),
            row.get("roster_status"),
            row.get("designation"),
            row.get("injury_status"),
        )

        status = roster_injury_status(
            raw_status
        )

        if not status:
            continue

        player = first_nonempty(
            row.get("player"),
            row.get("player_name"),
            row.get("full_name"),
            row.get("football_name"),
            row.get("name"),
        )

        team = normalize_team(
            first_nonempty(
                row.get("team"),
                row.get("team_abbr"),
                row.get("recent_team"),
            )
        )

        if not player or not team:
            continue

        results.append(
            {
                "player_id": first_nonempty(
                    row.get("player_id"),
                    row.get("gsis_id"),
                    row.get("id"),
                ),
                "espn_id": first_nonempty(
                    row.get("espn_id")
                ),
                "player": player,
                "team": team,
                "position": first_nonempty(
                    row.get("position"),
                    row.get("depth_chart_position"),
                    row.get("pos"),
                ).upper(),
                "status": status,
                "practice_status": "",
                "injury": first_nonempty(
                    row.get("injury"),
                    row.get("injury_description"),
                    row.get("body_part"),
                    raw_status,
                ),
                "source": "NFL roster",
                "source_updated": "",
            }
        )

    return results


STATUS_PRIORITY = {
    "IR": 100,
    "PUP": 95,
    "NFI": 95,
    "OUT": 90,
    "DOUBTFUL": 80,
    "QUESTIONABLE": 60,
    "INJURY": 40,
    "PROBABLE": 20,
    "ACTIVE": 0,
    "": 0,
}

SOURCE_PRIORITY = {
    "ESPN": 20,
    "NFL roster": 10,
}


def injury_priority(
    injury: dict[str, Any],
) -> tuple[int, int]:
    return (
        STATUS_PRIORITY.get(
            clean(
                injury.get("status")
            ).upper(),
            10,
        ),
        SOURCE_PRIORITY.get(
            clean(
                injury.get("source")
            ),
            0,
        ),
    )


def merge_missing_fields(
    preferred: dict[str, Any],
    other: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(preferred)

    for key in (
        "player_id",
        "espn_id",
        "player",
        "team",
        "position",
        "status",
        "practice_status",
        "injury",
        "source_updated",
    ):
        if not clean(
            merged.get(key)
        ):
            merged[key] = other.get(
                key,
                "",
            )

    return merged


def deduplicate(
    injuries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    deduped: dict[
        tuple[str, str],
        dict[str, Any]
    ] = {}

    for injury in injuries:
        team = normalize_team(
            injury.get("team")
        )

        player_id = clean(
            injury.get("player_id")
        )

        player = clean(
            injury.get("player")
        ).lower()

        identity = (
            player_id
            if player_id
            else player
        )

        if not team or not identity:
            continue

        key = (
            team,
            identity,
        )

        current = deduped.get(key)

        if current is None:
            deduped[key] = injury
            continue

        if injury_priority(
            injury
        ) > injury_priority(
            current
        ):
            deduped[key] = merge_missing_fields(
                injury,
                current,
            )
        else:
            deduped[key] = merge_missing_fields(
                current,
                injury,
            )

    rows = list(
        deduped.values()
    )

    rows.sort(
        key=lambda row: (
            row.get("team", ""),
            -injury_priority(row)[0],
            row.get("player", ""),
        )
    )

    return rows


def build_team_summary(
    injuries: list[dict[str, Any]],
) -> dict[str, Any]:
    teams: dict[str, dict[str, Any]] = {}

    for injury in injuries:
        team = normalize_team(
            injury.get("team")
        )

        if not team:
            continue

        summary = teams.setdefault(
            team,
            {
                "team": team,
                "total": 0,
                "out": 0,
                "doubtful": 0,
                "questionable": 0,
                "ir": 0,
                "pup": 0,
                "nfi": 0,
                "other": 0,
            },
        )

        summary["total"] += 1

        status = clean(
            injury.get("status")
        ).upper()

        mapping = {
            "OUT": "out",
            "DOUBTFUL": "doubtful",
            "QUESTIONABLE": "questionable",
            "IR": "ir",
            "PUP": "pup",
            "NFI": "nfi",
        }

        summary[
            mapping.get(
                status,
                "other",
            )
        ] += 1

    return teams


def build_nfl_injuries():
    print(
        "\n🏥 BUILDING NFL INJURY DATA\n"
    )

    generated_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    errors: list[str] = []
    espn_rows: list[
        dict[str, Any]
    ] = []
    teams: list[
        dict[str, str]
    ] = []

    # 1) Fastest source: one league-wide request.
    try:
        league_payload = fetch_json(
            ESPN_LEAGUE_INJURIES_URL
        )

        espn_rows = parse_league_injuries(
            league_payload
        )

        print(
            f"   ESPN league injury rows: "
            f"{len(espn_rows)}"
        )

    except Exception as exc:
        errors.append(
            f"league endpoint: {exc}"
        )

    # 2) If league endpoint is empty, use all team endpoints concurrently.
    if not espn_rows:
        try:
            teams_payload = fetch_json(
                ESPN_TEAMS_URL
            )

            teams = parse_espn_teams(
                teams_payload
            )

            print(
                f"   ESPN teams discovered: "
                f"{len(teams)}"
            )

            espn_rows, team_errors = (
                fetch_team_injuries_fast(
                    teams
                )
            )

            errors.extend(
                team_errors
            )

            print(
                f"   ESPN team injury rows: "
                f"{len(espn_rows)}"
            )

        except Exception as exc:
            errors.append(
                f"team discovery: {exc}"
            )

    roster_rows = (
        build_roster_reserve_injuries()
    )

    injuries = deduplicate(
        [
            *espn_rows,
            *roster_rows,
        ]
    )

    team_summary = build_team_summary(
        injuries
    )

    status_counts = {
        "OUT": 0,
        "DOUBTFUL": 0,
        "QUESTIONABLE": 0,
        "IR": 0,
        "PUP": 0,
        "NFI": 0,
        "INJURY": 0,
        "OTHER": 0,
    }

    source_counts = {
        "ESPN": 0,
        "NFL roster": 0,
        "OTHER": 0,
    }

    for injury in injuries:
        status = clean(
            injury.get("status")
        ).upper()

        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["OTHER"] += 1

        source = clean(
            injury.get("source")
        )

        if source in source_counts:
            source_counts[source] += 1
        else:
            source_counts["OTHER"] += 1

    output = {
        "season": CURRENT_SEASON,
        "generated_at": generated_at,

        "source": {
            "primary": (
                "ESPN Site API"
            ),
            "fallback": (
                "processed NFL roster reserve designations"
            ),
            "league_url": (
                ESPN_LEAGUE_INJURIES_URL
            ),
            "team_url_template": (
                ESPN_TEAM_INJURIES_URL
            ),
            "errors": errors,
        },

        "injury_count": len(
            injuries
        ),

        "team_count": len(
            team_summary
        ),

        "provider_counts": {
            "espn_raw": len(
                espn_rows
            ),
            "roster_reserve_raw": len(
                roster_rows
            ),
            "final": len(
                injuries
            ),
        },

        "status_counts": status_counts,
        "source_counts": source_counts,
        "teams": team_summary,
        "injuries": injuries,
    }

    save_json(
        output,
        OUTPUT_FILE,
    )

    save_json(
        output,
        WEB_OUTPUT_FILE,
    )

    print(
        f"   Roster reserve rows: "
        f"{len(roster_rows)}"
    )

    print(
        f"   Final injuries: "
        f"{len(injuries)}"
    )

    if errors:
        print(
            f"   Endpoint errors: "
            f"{len(errors)}"
        )

        for error in errors[:5]:
            print(
                f"      ⚠️ {error}"
            )

    print(
        f"\n   model: {OUTPUT_FILE}"
    )

    print(
        f"   web:   {WEB_OUTPUT_FILE}"
    )

    print(
        "\n✅ NFL INJURY DATA COMPLETE\n"
    )

    return output


if __name__ == "__main__":
    build_nfl_injuries()
