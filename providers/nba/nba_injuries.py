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
    "WSH": "WAS",
}

TEAM_NAMES = {
    "ATLANTA HAWKS": "ATL", "BOSTON CELTICS": "BOS",
    "BROOKLYN NETS": "BKN", "CHARLOTTE HORNETS": "CHA",
    "CHICAGO BULLS": "CHI", "CLEVELAND CAVALIERS": "CLE",
    "DALLAS MAVERICKS": "DAL", "DENVER NUGGETS": "DEN",
    "DETROIT PISTONS": "DET", "GOLDEN STATE WARRIORS": "GSW",
    "HOUSTON ROCKETS": "HOU", "INDIANA PACERS": "IND",
    "LOS ANGELES CLIPPERS": "LAC", "LA CLIPPERS": "LAC",
    "LOS ANGELES LAKERS": "LAL", "MEMPHIS GRIZZLIES": "MEM",
    "MIAMI HEAT": "MIA", "MILWAUKEE BUCKS": "MIL",
    "MINNESOTA TIMBERWOLVES": "MIN", "NEW ORLEANS PELICANS": "NOP",
    "NEW YORK KNICKS": "NYK", "OKLAHOMA CITY THUNDER": "OKC",
    "ORLANDO MAGIC": "ORL", "PHILADELPHIA 76ERS": "PHI",
    "PHOENIX SUNS": "PHX", "PORTLAND TRAIL BLAZERS": "POR",
    "SACRAMENTO KINGS": "SAC", "SAN ANTONIO SPURS": "SAS",
    "TORONTO RAPTORS": "TOR", "UTAH JAZZ": "UTA",
    "WASHINGTON WIZARDS": "WAS",
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

    return TEAM_NAMES.get(team, TEAM_ALIASES.get(team, team))


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
        entry.get("team") or athlete.get("team")
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
        injury.get("location")
        or injury.get("side")
        or entry.get("side")
    )

    details = injury.get("details") or {}

    if not isinstance(details, dict):
        details = {}

    detail = clean(
        entry.get("longComment")
        or entry.get("shortComment")
        or details.get("longComment")
        or details.get("shortComment")
        or injury.get("description")
        or entry.get("description")
    )

    return_date = clean(
        entry.get("returnDate")
        or entry.get("returnAt")
        or details.get("returnDate")
        or details.get("returnAt")
        or injury.get("returnDate")
        or entry.get("returnDate")
    )

    reported_date = clean(
        injury.get("date")
        or entry.get("date")
    )

    injury_description = " ".join(
        part for part in [injury_side, injury_type] if part
    )
    # ESPN sometimes places a status enum (INJURY_STATUS_OUT)
    # in the type field. Never display that as an injury diagnosis.
    if "INJURY_STATUS_" in injury_description.upper():
        injury_description = ""
    if not injury_description:
        for candidate in (
            injury.get("shortComment"),
            injury.get("longComment"),
            details.get("shortComment"),
            details.get("longComment"),
            entry.get("shortComment"),
            entry.get("longComment"),
            detail,
        ):
            candidate = clean(candidate)
            if candidate and "INJURY_STATUS_" not in candidate.upper():
                injury_description = candidate
                break

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
        "return_date_source": "ESPN" if return_date else "",
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
            group.get("team") or group.get("abbreviation")
            or group.get("displayName") or group.get("name")
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
# RETURN DATE FALLBACK — CBS SPORTS
# ESPN's league JSON currently omits returnDate for every injury.
# Use independently published estimated dates only when ESPN has none.
# ============================================================

def enrich_return_dates(rows: list[dict]) -> None:
    import re
    from bs4 import BeautifulSoup
    from datetime import date

    missing = [row for row in rows if not row["estimated_return_date"]]
    if not missing:
        return
    try:
        response = requests.get(
            "https://www.cbssports.com/nba/injuries/",
            headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"},
            timeout=25,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        matches = {}
        for tr in soup.select("tr"):
            cells = tr.find_all("td")
            if len(cells) < 5:
                continue
            name_cell = cells[0]
            links = name_cell.find_all("a")
            name = links[-1].get_text(" ", strip=True) if links else name_cell.get_text(" ", strip=True)
            name = " ".join(name.casefold().split())
            status_text = cells[-1].get_text(" ", strip=True)
            match = re.search(
                r"expected to be out until at least\s+"
                r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                r"[a-z]*\s+\d{1,2}(?:,?\s+\d{4})?)",
                status_text, re.IGNORECASE,
            )
            if name and match:
                matches[name] = match.group(1)
        filled = 0
        today = date.today()
        for row in missing:
            key = " ".join(row["player_name"].casefold().split())
            value = matches.get(key)
            if not value:
                continue
            # Keep the published month/day rather than inventing a year.
            row["estimated_return_date"] = value
            row["return_date_source"] = "CBS Sports"
            filled += 1
        print(
            f"CBS Sports estimated return dates: {filled}/{len(missing)} "
            f"(parsed {len(matches)} dated entries)", flush=True,
        )
    except (requests.RequestException, ValueError) as exc:
        print(f"CBS Sports return-date fallback unavailable: {exc}", flush=True)


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

    # Diagnose ESPN's actual response schema when estimated dates are missing.
    # Log only the first two player records to keep workflow output manageable.
    raw_samples = []
    for group in payload.get("injuries", []):
        if not isinstance(group, dict):
            continue
        entries = group.get("injuries")
        if not isinstance(entries, list):
            entries = [group]
        for entry in entries:
            if isinstance(entry, dict):
                raw_samples.append({
                    "player": (entry.get("athlete") or {}).get("displayName"),
                    "entry_keys": sorted(entry.keys()),
                    "entry_returnDate": entry.get("returnDate"),
                    "injury_keys": sorted((entry.get("injury") or {}).keys())
                        if isinstance(entry.get("injury"), dict) else [],
                    "injury_returnDate": (entry.get("injury") or {}).get("returnDate")
                        if isinstance(entry.get("injury"), dict) else None,
                })
                if len(raw_samples) == 2:
                    break
        if len(raw_samples) == 2:
            break
    print(f"ESPN injury schema samples: {json.dumps(raw_samples)}", flush=True)
    injuries = extract_injuries(payload)
    enrich_return_dates(injuries)
    print(f"ESPN estimated return dates available: {sum(bool(row['estimated_return_date']) for row in injuries)}/{len(injuries)}", flush=True)
    if not injuries:
        groups = payload.get("injuries", [])
        print(f"WARNING: ESPN returned {len(groups)} injury groups but 0 usable player records; refusing to publish an empty successful report.", flush=True)
        raise RuntimeError("NBA injury data empty or incompatible with ESPN response; existing published report left unchanged")

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
        "source": "ESPN (injuries); CBS Sports (estimated return fallback)",
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