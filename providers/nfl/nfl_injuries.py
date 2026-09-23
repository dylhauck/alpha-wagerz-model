from __future__ import annotations

import json
import re
import ssl
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

import certifi


MODEL_ROOT = Path(__file__).resolve().parents[2]
NFL_DIR = MODEL_ROOT / "data" / "processed" / "nfl"
WEB_NFL_DIR = MODEL_ROOT.parent / "alpha-wagerz-web" / "public" / "data" / "nfl"

OUTPUT_FILE = NFL_DIR / "injuries.json"
WEB_OUTPUT_FILE = WEB_NFL_DIR / "injuries.json"
ROSTERS_FILE = NFL_DIR / "rosters.json"

CURRENT_SEASON = 2026
ESPN_INJURIES_PAGE = "https://www.espn.com/nfl/injuries"
REQUEST_TIMEOUT = 15

TEAM_ALIASES = {
    "LA": "LAR",
    "JAC": "JAX",
    "WSH": "WAS",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LAR",
}

TEAM_NAME_TO_ABBR = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
}

TEAM_NAME_LOOKUP = {
    re.sub(r"\s+", " ", name).strip().lower(): abbr
    for name, abbr in TEAM_NAME_TO_ABBR.items()
}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


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


def save_json(payload: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def load_json(path: Path, default: Any):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def fetch_html(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        },
    )
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    with urlopen(
        request,
        timeout=REQUEST_TIMEOUT,
        context=ssl_context,
    ) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def extract_player_id_from_href(href: str) -> str:
    href = clean(href)
    if not href:
        return ""

    for pattern in (
        r"/player/_/id/(\d+)",
        r"/id/(\d+)(?:/|$)",
        r"[?&]id=(\d+)(?:&|$)",
    ):
        match = re.search(pattern, href)
        if match:
            return match.group(1)

    return ""


INJURY_ACRONYMS = {
    "ACL",
    "MCL",
    "PCL",
    "UCL",
    "LCL",
    "AC",
    "SC",
}

STATUS_ONLY_INJURY_VALUES = {
    "",
    "OUT",
    "IR",
    "INJURED RESERVE",
    "INJURED-RESERVE",
    "RESERVE/INJURED",
    "RESERVE-INJURED",
    "QUESTIONABLE",
    "DOUBTFUL",
    "PROBABLE",
    "ACTIVE",
    "PUP",
    "RESERVE/PUP",
    "NFI",
    "RESERVE/NFI",
    "INJURY",
}


def format_injury_label(value: Any) -> str:
    text = clean(value)

    if not text:
        return "Undisclosed"

    if text.upper() in STATUS_ONLY_INJURY_VALUES:
        return "Undisclosed"

    words = re.split(r"(\s+|-)", text)
    formatted: list[str] = []

    for word in words:
        if not word or word.isspace() or word == "-":
            formatted.append(word)
            continue

        stripped = re.sub(r"[^A-Za-z]", "", word).upper()

        if stripped in INJURY_ACRONYMS:
            suffix_match = re.search(r"([^A-Za-z]+)$", word)
            suffix = suffix_match.group(1) if suffix_match else ""
            formatted.append(stripped + suffix)
        else:
            formatted.append(
                word[:1].upper() + word[1:].lower()
            )

    result = "".join(formatted).strip()
    return result or "Undisclosed"


def extract_injury_description(
    comment: str,
    status_raw: Any = "",
) -> str:
    """
    Return the most specific injury description ESPN actually provides.

    Do not infer a diagnosis. Prefer a specific diagnosis/condition if ESPN
    explicitly states one; otherwise use the useful parenthetical body part
    ESPN provides. If neither exists, return Undisclosed.
    """
    comment = clean(comment)

    if not comment:
        return "Undisclosed"

    patterns = (
        r"\b(?:torn|ruptured)\s+(?:left\s+|right\s+)?(?:ACL|MCL|PCL|LCL|UCL|Achilles|meniscus|pectoral)\b",
        r"\b(?:ACL|MCL|PCL|LCL|UCL|meniscus|Achilles|pectoral)\s+(?:tear|rupture|sprain|strain)\b",
        r"\bhigh[- ]ankle sprain\b",
        r"\b(?:left\s+|right\s+)?ankle sprain\b",
        r"\b(?:left\s+|right\s+)?hamstring strain\b",
        r"\b(?:left\s+|right\s+)?groin strain\b",
        r"\b(?:left\s+|right\s+)?calf strain\b",
        r"\b(?:left\s+|right\s+)?quad(?:riceps)? strain\b",
        r"\b(?:left\s+|right\s+)?shoulder sprain\b",
        r"\b(?:left\s+|right\s+)?wrist sprain\b",
        r"\b(?:left\s+|right\s+)?knee sprain\b",
        r"\b(?:left\s+|right\s+)?foot sprain\b",
        r"\b(?:left\s+|right\s+)?hip flexor strain\b",
        r"\b(?:left\s+|right\s+)?abdominal strain\b",
        r"\bturf toe\b",
        r"\bplantar fasciitis\b",
        r"\bconcussion\b",
        r"\b(?:left\s+|right\s+)?(?:hand|wrist|arm|elbow|shoulder|chest|rib|back|neck|hip|groin|hamstring|quad|calf|knee|ankle|foot|toe)\s+(?:fracture|sprain|strain|tear)\b",
        r"\bfractured\s+(?:left\s+|right\s+)?(?:hand|wrist|arm|elbow|shoulder|rib|hip|knee|ankle|foot|toe)\b",
        r"\bbroken\s+(?:left\s+|right\s+)?(?:hand|wrist|arm|elbow|shoulder|rib|hip|knee|ankle|foot|toe)\b",
        r"\bdislocated\s+(?:left\s+|right\s+)?(?:shoulder|elbow|finger|hip|knee)\b",
    )

    for pattern in patterns:
        match = re.search(pattern, comment, flags=re.IGNORECASE)
        if match:
            return format_injury_label(match.group(0))

    # ESPN commonly places the injury/body part in parentheses after the name.
    for raw_candidate in re.findall(r"\(([^()]{2,80})\)", comment):
        candidate = clean(raw_candidate)

        if not candidate:
            continue

        if candidate.upper() in {
            "AP",
            "IR",
            "NFI",
            "PUP",
            "NFL",
            "OUT",
            "QUESTIONABLE",
            "DOUBTFUL",
            "PROBABLE",
            "ACTIVE",
        }:
            continue

        if re.fullmatch(
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?\.?\s*"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
            r"\.?\s+\d{1,2}(?:,\s*\d{4})?",
            candidate,
            flags=re.IGNORECASE,
        ):
            continue

        if re.fullmatch(
            r"\d{1,2}[-/]\d{1,2}(?:[-/]\d{2,4})?",
            candidate,
        ):
            continue

        return format_injury_label(candidate)

    generic_match = re.search(
        r"\b(?:left\s+|right\s+)?"
        r"(?:head|face|neck|shoulder|arm|elbow|forearm|wrist|hand|finger|"
        r"chest|rib|back|abdomen|abdominal|hip|groin|hamstring|quad|thigh|"
        r"knee|calf|shin|ankle|foot|toe)\s+injury\b",
        comment,
        flags=re.IGNORECASE,
    )

    if generic_match:
        value = re.sub(
            r"\s+injury$",
            "",
            generic_match.group(0),
            flags=re.IGNORECASE,
        )
        return format_injury_label(value)

    return "Undisclosed"


class ESPNInjuriesHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.current_team = ""
        self.rows: list[dict[str, Any]] = []

        self.tag_stack: list[str] = []
        self.text_stack: list[list[str]] = []
        self.class_stack: list[str] = []

        self.in_tr = False
        self.in_td = False
        self.current_cells: list[str] = []
        self.current_cell_text: list[str] = []
        self.current_player_href = ""
        self.first_player_link_seen = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        self.tag_stack.append(tag)
        self.text_stack.append([])
        self.class_stack.append(attrs_dict.get("class", ""))

        if tag == "tr":
            self.in_tr = True
            self.current_cells = []
            self.current_player_href = ""
            self.first_player_link_seen = False

        elif tag == "td" and self.in_tr:
            self.in_td = True
            self.current_cell_text = []

        elif tag == "a" and self.in_tr and not self.first_player_link_seen:
            href = attrs_dict.get("href", "")
            if "/nfl/player/" in href or "/player/_/id/" in href:
                self.current_player_href = href
                self.first_player_link_seen = True

    def handle_data(self, data: str) -> None:
        text = clean(unescape(data))
        if not text:
            return

        if self.text_stack:
            self.text_stack[-1].append(text)

        if self.in_td:
            self.current_cell_text.append(text)

        team = TEAM_NAME_LOOKUP.get(text.lower())
        if team:
            self.current_team = team

    def handle_endtag(self, tag: str) -> None:
        if self.tag_stack:
            start_tag = self.tag_stack.pop()
            texts = self.text_stack.pop()
            class_name = self.class_stack.pop()
            captured = clean(" ".join(texts))

            if self.text_stack and captured:
                self.text_stack[-1].append(captured)

            if start_tag == tag and captured and "Table__Title" in class_name:
                team = TEAM_NAME_LOOKUP.get(captured.lower())
                if team:
                    self.current_team = team

        if tag == "td" and self.in_td:
            self.current_cells.append(
                clean(" ".join(self.current_cell_text))
            )
            self.current_cell_text = []
            self.in_td = False

        elif tag == "tr" and self.in_tr:
            self._finish_row()
            self.in_tr = False
            self.in_td = False
            self.current_cells = []
            self.current_cell_text = []
            self.current_player_href = ""
            self.first_player_link_seen = False

    def _finish_row(self) -> None:
        cells = [clean(cell) for cell in self.current_cells]

        if not self.current_team or len(cells) < 4:
            return

        if cells[0].upper() in {"NAME", "PLAYER"}:
            return

        player = cells[0]
        position = cells[1] if len(cells) > 1 else ""
        return_date = cells[2] if len(cells) > 2 else ""
        status_raw = cells[3] if len(cells) > 3 else ""
        comment = cells[4] if len(cells) > 4 else ""

        status = normalize_status(status_raw)
        if not player or not status:
            return

        player_id = extract_player_id_from_href(
            self.current_player_href
        )
        injury_description = extract_injury_description(
            comment,
            status_raw,
        )

        self.rows.append(
            {
                "player_id": player_id,
                "espn_id": player_id,
                "player": player,
                "team": normalize_team(self.current_team),
                "position": position.upper(),
                "status": status,
                "practice_status": "",
                "injury": injury_description,
                "detail": comment,
                "estimated_return_date": return_date,
                "source": "ESPN",
                "source_updated": "",
            }
        )


def parse_espn_injuries_html(html: str) -> list[dict[str, Any]]:
    parser = ESPNInjuriesHTMLParser()
    parser.feed(html)
    parser.close()
    return parser.rows


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

    if "PUP" in raw or "PHYSICALLY UNABLE" in raw:
        return "PUP"

    if (
        "NFI" in raw
        or "NON-FOOTBALL INJURY" in raw
        or "NON FOOTBALL INJURY" in raw
    ):
        return "NFI"

    return ""


def extract_roster_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]

    if isinstance(payload, dict):
        for key in ("players", "rosters", "roster", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]

    return []


def build_roster_reserve_injuries() -> list[dict[str, Any]]:
    rows = extract_roster_rows(load_json(ROSTERS_FILE, default=[]))
    results: list[dict[str, Any]] = []

    for row in rows:
        raw_status = first_nonempty(
            row.get("status"),
            row.get("roster_status"),
            row.get("designation"),
            row.get("injury_status"),
        )

        status = roster_injury_status(raw_status)
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
                "espn_id": first_nonempty(row.get("espn_id")),
                "player": player,
                "team": team,
                "position": first_nonempty(
                    row.get("position"),
                    row.get("depth_chart_position"),
                    row.get("pos"),
                ).upper(),
                "status": status,
                "practice_status": "",
                "injury": format_injury_label(
                    first_nonempty(
                        row.get("injury"),
                        row.get("injury_description"),
                        row.get("body_part"),
                    )
                ),
                "detail": "",
                "estimated_return_date": "",
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
            clean(injury.get("status")).upper(),
            10,
        ),
        SOURCE_PRIORITY.get(
            clean(injury.get("source")),
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
        "detail",
        "estimated_return_date",
        "source_updated",
    ):
        if not clean(merged.get(key)):
            merged[key] = other.get(key, "")

    return merged


def deduplicate(
    injuries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}

    for injury in injuries:
        team = normalize_team(injury.get("team"))
        player_id = clean(injury.get("player_id"))
        player = clean(injury.get("player")).lower()
        identity = player_id if player_id else player

        if not team or not identity:
            continue

        key = (team, identity)
        current = deduped.get(key)

        if current is None:
            deduped[key] = injury
            continue

        if injury_priority(injury) > injury_priority(current):
            deduped[key] = merge_missing_fields(injury, current)
        else:
            deduped[key] = merge_missing_fields(current, injury)

    rows = list(deduped.values())
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
        team = normalize_team(injury.get("team"))
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
        status = clean(injury.get("status")).upper()

        mapping = {
            "OUT": "out",
            "DOUBTFUL": "doubtful",
            "QUESTIONABLE": "questionable",
            "IR": "ir",
            "PUP": "pup",
            "NFI": "nfi",
        }

        summary[mapping.get(status, "other")] += 1

    return teams


def existing_nonempty_output() -> dict[str, Any]:
    for path in (OUTPUT_FILE, WEB_OUTPUT_FILE):
        payload = load_json(path, default={})

        if (
            isinstance(payload, dict)
            and isinstance(payload.get("injuries"), list)
            and payload.get("injuries")
        ):
            return payload

    return {}


def build_nfl_injuries():
    print("\n🏥 BUILDING NFL INJURY DATA\n")

    generated_at = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []
    espn_rows: list[dict[str, Any]] = []

    try:
        html = fetch_html(ESPN_INJURIES_PAGE)
        espn_rows = parse_espn_injuries_html(html)

        print(
            f"   ESPN page injury rows: {len(espn_rows)}"
        )

        if not espn_rows:
            errors.append(
                "ESPN injuries page loaded but no injury rows were parsed"
            )

    except Exception as exc:
        errors.append(
            f"ESPN injuries page: {exc}"
        )

    roster_rows = build_roster_reserve_injuries()

    print(
        f"   Roster reserve rows: {len(roster_rows)}"
    )

    if not espn_rows and not roster_rows:
        previous = existing_nonempty_output()

        if previous:
            print(
                "   ⚠️ No fresh rows available; preserving existing non-empty injuries.json."
            )

            for error in errors[:5]:
                print(f"      ⚠️ {error}")

            return previous

    injuries = deduplicate(
        [
            *espn_rows,
            *roster_rows,
        ]
    )

    team_summary = build_team_summary(injuries)

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
        status = clean(injury.get("status")).upper()
        if status in status_counts:
            status_counts[status] += 1
        else:
            status_counts["OTHER"] += 1

        source = clean(injury.get("source"))
        if source in source_counts:
            source_counts[source] += 1
        else:
            source_counts["OTHER"] += 1

    output = {
        "season": CURRENT_SEASON,
        "generated_at": generated_at,
        "source": {
            "primary": "ESPN NFL injuries page",
            "fallback": "processed NFL roster reserve designations",
            "url": ESPN_INJURIES_PAGE,
            "errors": errors,
        },
        "injury_count": len(injuries),
        "team_count": len(team_summary),
        "provider_counts": {
            "espn_raw": len(espn_rows),
            "roster_reserve_raw": len(roster_rows),
            "final": len(injuries),
        },
        "status_counts": status_counts,
        "source_counts": source_counts,
        "teams": team_summary,
        "injuries": injuries,
    }

    save_json(output, OUTPUT_FILE)
    save_json(output, WEB_OUTPUT_FILE)

    print(
        f"   Final injuries: {len(injuries)}"
    )
    print(
        f"   Teams with injuries: {len(team_summary)}"
    )

    if errors:
        print(
            f"   Source warnings: {len(errors)}"
        )
        for error in errors[:5]:
            print(f"      ⚠️ {error}")

    print(f"\n   model: {OUTPUT_FILE}")
    print(f"   web:   {WEB_OUTPUT_FILE}")
    print("\n✅ NFL INJURY DATA COMPLETE\n")

    return output


if __name__ == "__main__":
    build_nfl_injuries()


