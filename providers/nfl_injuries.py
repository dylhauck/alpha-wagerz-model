import json
import ssl
import certifi

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


# =========================================================
# PATHS
# =========================================================

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


# =========================================================
# ESPN
# =========================================================

ESPN_INJURIES_URL = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/football/nfl/injuries"
)

REQUEST_TIMEOUT = 20


# =========================================================
# TEAM NORMALIZATION
# =========================================================

TEAM_ALIASES = {
    "LA": "LAR",
    "JAC": "JAX",
    "WSH": "WAS",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}


def normalize_team(value: Any) -> str:
    team = str(value or "").strip().upper()

    return TEAM_ALIASES.get(
        team,
        team,
    )


# =========================================================
# GENERAL HELPERS
# =========================================================

def clean(value: Any) -> str:
    return str(value or "").strip()


def first_nonempty(
    *values: Any,
) -> str:
    for value in values:
        text = clean(value)

        if text:
            return text

    return ""


def save_json(
    payload: Any,
    path: Path,
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            ensure_ascii=False,
        )


def fetch_json(
    url: str,
) -> dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": (
                "Alpha-Wagerz/1.0 "
                "(NFL injury data)"
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
            response.read().decode(
                "utf-8"
            )
        )


# =========================================================
# STATUS NORMALIZATION
# =========================================================

def normalize_status(
    value: Any,
) -> str:
    status = clean(
        value
    ).upper()

    aliases = {
        "Q": "QUESTIONABLE",
        "QUES": "QUESTIONABLE",

        "D": "DOUBTFUL",

        "O": "OUT",

        "IR": "IR",
        "INJURED RESERVE": "IR",
        "RESERVE/INJURED": "IR",

        "PUP": "PUP",
        "PHYSICALLY UNABLE TO PERFORM": "PUP",

        "NFI": "NFI",
        "NON-FOOTBALL INJURY": "NFI",

        "ACTIVE": "ACTIVE",

        "PROBABLE": "PROBABLE",
    }

    return aliases.get(
        status,
        status,
    )


def normalize_practice_status(
    value: Any,
) -> str:
    status = clean(
        value
    ).upper()

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

    return aliases.get(
        status,
        status,
    )


# =========================================================
# ESPN FIELD HELPERS
# =========================================================

def extract_status(
    injury: dict[str, Any],
) -> str:
    status = injury.get(
        "status"
    )

    if isinstance(
        status,
        dict,
    ):
        status = first_nonempty(
            status.get(
                "name"
            ),
            status.get(
                "description"
            ),
            status.get(
                "abbreviation"
            ),
            status.get(
                "type"
            ),
        )

    return normalize_status(
        status
    )


def extract_practice_status(
    injury: dict[str, Any],
) -> str:
    practice = (
        injury.get(
            "practiceStatus"
        )
        or injury.get(
            "practice_status"
        )
    )

    if isinstance(
        practice,
        dict,
    ):
        practice = first_nonempty(
            practice.get(
                "name"
            ),
            practice.get(
                "description"
            ),
            practice.get(
                "abbreviation"
            ),
        )

    return normalize_practice_status(
        practice
    )


def extract_injury_description(
    injury: dict[str, Any],
) -> str:
    details = injury.get(
        "details"
    )

    detail_text = ""

    if isinstance(
        details,
        dict,
    ):
        detail_text = first_nonempty(
            details.get(
                "detail"
            ),
            details.get(
                "type"
            ),
            details.get(
                "location"
            ),
            details.get(
                "side"
            ),
        )

    return first_nonempty(
        injury.get(
            "shortComment"
        ),
        injury.get(
            "longComment"
        ),
        injury.get(
            "type"
        ),
        injury.get(
            "description"
        ),
        detail_text,
    )


# =========================================================
# PLAYER NORMALIZATION
# =========================================================

def normalize_injury(
    team_abbr: str,
    raw: dict[str, Any],
) -> dict[str, Any]:
    athlete = raw.get(
        "athlete"
    )

    if not isinstance(
        athlete,
        dict,
    ):
        athlete = {}

    position = athlete.get(
        "position"
    )

    if not isinstance(
        position,
        dict,
    ):
        position = {}

    player_id = first_nonempty(
        athlete.get(
            "id"
        ),
        raw.get(
            "athleteId"
        ),
        raw.get(
            "playerId"
        ),
    )

    player = first_nonempty(
        athlete.get(
            "fullName"
        ),
        athlete.get(
            "displayName"
        ),
        athlete.get(
            "shortName"
        ),
        raw.get(
            "name"
        ),
    )

    pos = first_nonempty(
        position.get(
            "abbreviation"
        ),
        position.get(
            "name"
        ),
        raw.get(
            "position"
        ),
    ).upper()

    status = extract_status(
        raw
    )

    practice_status = (
        extract_practice_status(
            raw
        )
    )

    injury_description = (
        extract_injury_description(
            raw
        )
    )

    return {
        "player_id": player_id,
        "espn_id": player_id,

        "player": player,

        "team": normalize_team(
            team_abbr
        ),

        "position": pos,

        "status": status,

        "practice_status": (
            practice_status
        ),

        "injury": (
            injury_description
        ),

        "source": "ESPN",

        "source_updated": first_nonempty(
            raw.get(
                "date"
            ),
            raw.get(
                "lastUpdated"
            ),
        ),
    }


# =========================================================
# PARSE ESPN RESPONSE
# =========================================================

def parse_espn_injuries(
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    results: list[
        dict[str, Any]
    ] = []

    groups = payload.get(
        "injuries",
        []
    )

    if not isinstance(
        groups,
        list,
    ):
        return results

    for group in groups:
        if not isinstance(
            group,
            dict,
        ):
            continue

        team = group.get(
            "team"
        )

        if not isinstance(
            team,
            dict,
        ):
            team = {}

        team_abbr = normalize_team(
            first_nonempty(
                team.get(
                    "abbreviation"
                ),
                team.get(
                    "shortDisplayName"
                ),
            )
        )

        if not team_abbr:
            continue

        injuries = group.get(
            "injuries",
            []
        )

        if not isinstance(
            injuries,
            list,
        ):
            continue

        for injury in injuries:
            if not isinstance(
                injury,
                dict,
            ):
                continue

            normalized = normalize_injury(
                team_abbr,
                injury,
            )

            if not normalized[
                "player"
            ]:
                continue

            results.append(
                normalized
            )

    return results


# =========================================================
# DEDUPLICATION
# =========================================================

STATUS_PRIORITY = {
    "IR": 100,
    "PUP": 95,
    "NFI": 95,

    "OUT": 90,
    "DOUBTFUL": 80,
    "QUESTIONABLE": 60,
    "PROBABLE": 20,

    "ACTIVE": 0,
    "": 0,
}


def injury_priority(
    injury: dict[str, Any],
) -> int:
    status = injury.get(
        "status",
        "",
    )

    return STATUS_PRIORITY.get(
        status,
        10,
    )


def deduplicate(
    injuries: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    deduped: dict[
        tuple[str, str],
        dict[str, Any]
    ] = {}

    for injury in injuries:
        team = normalize_team(
            injury.get(
                "team"
            )
        )

        player_id = clean(
            injury.get(
                "player_id"
            )
        )

        player = clean(
            injury.get(
                "player"
            )
        ).lower()

        identity = (
            player_id
            if player_id
            else player
        )

        if not identity:
            continue

        key = (
            team,
            identity,
        )

        current = deduped.get(
            key
        )

        if (
            current is None
            or injury_priority(
                injury
            )
            > injury_priority(
                current
            )
        ):
            deduped[
                key
            ] = injury

    rows = list(
        deduped.values()
    )

    rows.sort(
        key=lambda row: (
            row.get(
                "team",
                "",
            ),
            -injury_priority(
                row
            ),
            row.get(
                "player",
                "",
            ),
        )
    )

    return rows


# =========================================================
# SUMMARY
# =========================================================

def build_team_summary(
    injuries: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    teams: dict[
        str,
        dict[str, Any]
    ] = {}

    for injury in injuries:
        team = normalize_team(
            injury.get(
                "team"
            )
        )

        if not team:
            continue

        if team not in teams:
            teams[
                team
            ] = {
                "team": team,
                "total": 0,

                "out": 0,
                "doubtful": 0,
                "questionable": 0,

                "ir": 0,
                "pup": 0,
                "nfi": 0,
            }

        summary = teams[
            team
        ]

        summary[
            "total"
        ] += 1

        status = injury.get(
            "status"
        )

        if status == "OUT":
            summary[
                "out"
            ] += 1

        elif status == "DOUBTFUL":
            summary[
                "doubtful"
            ] += 1

        elif status == "QUESTIONABLE":
            summary[
                "questionable"
            ] += 1

        elif status == "IR":
            summary[
                "ir"
            ] += 1

        elif status == "PUP":
            summary[
                "pup"
            ] += 1

        elif status == "NFI":
            summary[
                "nfi"
            ] += 1

    return teams


# =========================================================
# BUILD
# =========================================================

def build_nfl_injuries():
    print(
        "\n🏥 BUILDING NFL "
        "INJURY DATA\n"
    )

    try:
        payload = fetch_json(
            ESPN_INJURIES_URL
        )

    except Exception as exc:
        print(
            "   ❌ ESPN injury "
            f"request failed: {exc}"
        )

        print(
            "   Existing injury file "
            "will NOT be overwritten."
        )

        raise

    season = payload.get(
        "season",
        {}
    )

    if not isinstance(
        season,
        dict,
    ):
        season = {}

    season_year = season.get(
        "year"
    )

    print(
        "   ESPN season: "
        f"{season_year or 'unknown'}"
    )

    raw_injuries = (
        parse_espn_injuries(
            payload
        )
    )

    injuries = deduplicate(
        raw_injuries
    )

    team_summary = (
        build_team_summary(
            injuries
        )
    )

    status_counts = {
        "OUT": 0,
        "DOUBTFUL": 0,
        "QUESTIONABLE": 0,
        "IR": 0,
        "PUP": 0,
        "NFI": 0,
        "OTHER": 0,
    }

    for injury in injuries:
        status = injury.get(
            "status"
        )

        if status in status_counts:
            status_counts[
                status
            ] += 1
        else:
            status_counts[
                "OTHER"
            ] += 1

    generated_at = (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )

    output = {
        "season": season_year,

        "generated_at": (
            generated_at
        ),

        "source": "ESPN",

        "source_url": (
            ESPN_INJURIES_URL
        ),

        "injury_count": len(
            injuries
        ),

        "team_count": len(
            team_summary
        ),

        "status_counts": (
            status_counts
        ),

        "teams": team_summary,

        "injuries": injuries,
    }

    # Critical safety check:
    #
    # Do not overwrite good injury
    # data with an unexpectedly empty
    # response during the NFL season.

    if not injuries:
        print(
            "   ⚠️ ESPN returned zero "
            "injury rows."
        )

        print(
            "   Injury files were NOT "
            "overwritten."
        )

        return output

    save_json(
        output,
        OUTPUT_FILE,
    )

    save_json(
        output,
        WEB_OUTPUT_FILE,
    )

    print(
        f"   Relevant injuries: "
        f"{len(injuries)}"
    )

    print(
        f"   Teams represented: "
        f"{len(team_summary)}"
    )

    print(
        "\n   Status counts"
    )

    for status, count in (
        status_counts.items()
    ):
        print(
            f"      {status}: "
            f"{count}"
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
        "\n✅ NFL INJURY "
        "DATA COMPLETE\n"
    )

    return output


if __name__ == "__main__":
    build_nfl_injuries()