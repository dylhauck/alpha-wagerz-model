from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from nba_api.stats.endpoints import commonteamroster
from nba_api.stats.static import teams as nba_teams


# ============================================================
# PATHS
# ============================================================

MODEL_ROOT = Path(__file__).resolve().parents[1]

NBA_DIR = MODEL_ROOT / "data" / "processed" / "nba"

WEB_NBA_DIR = (
    MODEL_ROOT.parent
    / "alpha-wagerz-web"
    / "public"
    / "data"
    / "nba"
)

OUTPUT_FILE = NBA_DIR / "players.json"
WEB_OUTPUT_FILE = WEB_NBA_DIR / "players.json"


# ============================================================
# CONFIG
# ============================================================

CURRENT_SEASON = "2026-27"

REQUEST_TIMEOUT = 60

# NBA Stats can become unhappy when hit too quickly.
REQUEST_DELAY_SECONDS = 0.75

# Number of retries for an individual team.
MAX_RETRIES = 3


# ============================================================
# HELPERS
# ============================================================

def clean_text(value: Any) -> str:
    if value is None:
        return ""

    try:
        if value != value:  # NaN
            return ""
    except Exception:
        pass

    return str(value).strip()


def clean_int(value: Any) -> int | None:
    if value is None:
        return None

    try:
        if value != value:  # NaN
            return None
    except Exception:
        pass

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_position(value: Any) -> str:
    """
    Preserve the position supplied by NBA.com while normalizing
    whitespace and separators.

    Examples:
        "G"   -> "G"
        "F"   -> "F"
        "C"   -> "C"
        "G-F" -> "G-F"
        "F-G" -> "F-G"
        "F-C" -> "F-C"
        "C-F" -> "C-F"

    We intentionally do NOT invent PG/SG/SF/PF assignments.
    """
    position = clean_text(value).upper()

    if not position:
        return "N/A"

    position = position.replace("/", "-")
    position = position.replace(" ", "")

    return position


def position_group(position: str) -> str:
    """
    Gives the frontend a broader filter group while retaining the
    exact NBA.com position in `position`.

    Examples:
        G   -> G
        G-F -> G/F
        F-G -> G/F
        F   -> F
        F-C -> F/C
        C-F -> F/C
        C   -> C
    """
    pos = normalize_position(position)

    if pos == "G":
        return "G"

    if pos == "F":
        return "F"

    if pos == "C":
        return "C"

    parts = {part for part in pos.split("-") if part}

    if parts == {"G", "F"}:
        return "G/F"

    if parts == {"F", "C"}:
        return "F/C"

    if parts == {"G", "C"}:
        return "G/C"

    return pos


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            ensure_ascii=False,
        )


# ============================================================
# TEAM REFERENCE
# ============================================================

def get_nba_teams() -> list[dict[str, Any]]:
    """
    Uses nba_api's static NBA team directory.

    This avoids hardcoding all 30 NBA team IDs ourselves.
    """
    teams = nba_teams.get_teams()

    cleaned: list[dict[str, Any]] = []

    for team in teams:
        team_id = clean_int(team.get("id"))
        abbreviation = clean_text(team.get("abbreviation")).upper()

        if team_id is None or not abbreviation:
            continue

        cleaned.append(
            {
                "team_id": team_id,
                "abbr": abbreviation,
                "city": clean_text(team.get("city")),
                "nickname": clean_text(team.get("nickname")),
                "full_name": clean_text(team.get("full_name")),
            }
        )

    cleaned.sort(key=lambda item: item["abbr"])

    return cleaned


# ============================================================
# ROSTER REQUEST
# ============================================================

def fetch_team_roster(
    team: dict[str, Any],
) -> list[dict[str, Any]]:
    team_id = team["team_id"]
    team_abbr = team["abbr"]

    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(
                f"  Fetching {team_abbr} roster "
                f"(attempt {attempt}/{MAX_RETRIES})..."
            )

            response = commonteamroster.CommonTeamRoster(
                team_id=team_id,
                season=CURRENT_SEASON,
                league_id_nullable="00",
                timeout=REQUEST_TIMEOUT,
            )

            frame = response.common_team_roster.get_data_frame()

            if frame is None or frame.empty:
                print(f"    WARNING: {team_abbr} returned an empty roster.")
                return []

            players: list[dict[str, Any]] = []

            for _, row in frame.iterrows():
                player_id = clean_int(row.get("PLAYER_ID"))
                player_name = clean_text(row.get("PLAYER"))

                if player_id is None or not player_name:
                    continue

                position = normalize_position(row.get("POSITION"))

                players.append(
                    {
                        "player_id": player_id,
                        "player_name": player_name,
                        "team_id": team_id,
                        "team": team_abbr,
                        "team_name": team["full_name"],
                        "number": clean_text(row.get("NUM")),
                        "position": position,
                        "position_group": position_group(position),
                        "height": clean_text(row.get("HEIGHT")),
                        "weight": clean_text(row.get("WEIGHT")),
                        "age": (
                            float(row.get("AGE"))
                            if row.get("AGE") is not None
                            and str(row.get("AGE")) != "nan"
                            else None
                        ),
                        "experience": clean_text(row.get("EXP")),
                        "school": clean_text(row.get("SCHOOL")),
                    }
                )

            players.sort(
                key=lambda item: (
                    item["position"],
                    item["player_name"],
                )
            )

            print(
                f"    {team_abbr}: "
                f"{len(players)} players"
            )

            return players

        except Exception as exc:
            last_error = exc

            print(
                f"    ERROR fetching {team_abbr}: {exc}"
            )

            if attempt < MAX_RETRIES:
                wait_seconds = attempt * 2

                print(
                    f"    Retrying in {wait_seconds} seconds..."
                )

                time.sleep(wait_seconds)

    raise RuntimeError(
        f"Unable to fetch {team_abbr} roster after "
        f"{MAX_RETRIES} attempts: {last_error}"
    )


# ============================================================
# BUILD PLAYER REFERENCE
# ============================================================

def build_players() -> dict[str, Any]:
    print()
    print("=" * 70)
    print("BUILDING NBA PLAYER / ROSTER REFERENCE")
    print("=" * 70)
    print(f"Season: {CURRENT_SEASON}")
    print()

    teams = get_nba_teams()

    print(f"NBA teams found: {len(teams)}")

    if len(teams) != 30:
        print(
            f"WARNING: Expected 30 NBA teams, found {len(teams)}."
        )

    all_players: list[dict[str, Any]] = []
    team_rosters: dict[str, list[dict[str, Any]]] = {}

    failed_teams: list[str] = []

    for index, team in enumerate(teams, start=1):
        abbr = team["abbr"]

        print()
        print(
            f"[{index}/{len(teams)}] "
            f"{team['full_name']} ({abbr})"
        )

        try:
            roster = fetch_team_roster(team)

            team_rosters[abbr] = roster
            all_players.extend(roster)

        except Exception as exc:
            print(f"FAILED: {abbr}: {exc}")

            failed_teams.append(abbr)
            team_rosters[abbr] = []

        if index < len(teams):
            time.sleep(REQUEST_DELAY_SECONDS)

    # --------------------------------------------------------
    # Remove accidental duplicate player/team rows.
    # --------------------------------------------------------

    unique_players: dict[tuple[int, str], dict[str, Any]] = {}

    for player in all_players:
        key = (
            player["player_id"],
            player["team"],
        )

        unique_players[key] = player

    all_players = list(unique_players.values())

    all_players.sort(
        key=lambda item: (
            item["team"],
            item["player_name"],
        )
    )

    # --------------------------------------------------------
    # Useful lookup structures
    # --------------------------------------------------------

    by_player_id = {
        str(player["player_id"]): player
        for player in all_players
    }

    by_team: dict[str, list[int]] = {}

    for team in teams:
        abbr = team["abbr"]

        by_team[abbr] = [
            player["player_id"]
            for player in team_rosters.get(abbr, [])
        ]

    # --------------------------------------------------------
    # Payload
    # --------------------------------------------------------

    payload = {
        "season": CURRENT_SEASON,
        "league": "NBA",
        "team_count": len(teams),
        "player_count": len(all_players),
        "failed_teams": failed_teams,
        "teams": teams,
        "players": all_players,
        "by_team": by_team,
        "by_player_id": by_player_id,
    }

    return payload


# ============================================================
# SAVE
# ============================================================

def save_players(payload: dict[str, Any]) -> None:
    print()
    print("=" * 70)
    print("SAVING NBA PLAYER DATA")
    print("=" * 70)

    write_json(
        OUTPUT_FILE,
        payload,
    )

    print(f"Model: {OUTPUT_FILE}")

    try:
        write_json(
            WEB_OUTPUT_FILE,
            payload,
        )

        print(f"Web:   {WEB_OUTPUT_FILE}")

    except Exception as exc:
        print(
            "WARNING: Could not write NBA players to web repo:"
        )
        print(f"  {exc}")


# ============================================================
# VALIDATION
# ============================================================

def validate_players(payload: dict[str, Any]) -> None:
    players = payload.get("players", [])
    teams = payload.get("teams", [])
    failed_teams = payload.get("failed_teams", [])

    print()
    print("=" * 70)
    print("NBA PLAYER DATA SUMMARY")
    print("=" * 70)

    print(f"Teams:   {len(teams)}")
    print(f"Players: {len(players)}")

    if failed_teams:
        print(
            "Failed teams: "
            + ", ".join(failed_teams)
        )
    else:
        print("Failed teams: none")

    print()

    positions: dict[str, int] = {}

    for player in players:
        position = player.get("position", "N/A")

        positions[position] = (
            positions.get(position, 0) + 1
        )

    print("Position counts:")

    for position, count in sorted(
        positions.items(),
        key=lambda item: (-item[1], item[0]),
    ):
        print(f"  {position:<6} {count}")

    print()

    if not players:
        raise RuntimeError(
            "NBA player build returned zero players."
        )

    if failed_teams:
        raise RuntimeError(
            "NBA player build was incomplete. "
            "Failed teams: "
            + ", ".join(failed_teams)
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    payload = build_players()

    validate_players(payload)

    save_players(payload)

    print()
    print("=" * 70)
    print("NBA PLAYER / ROSTER BUILD COMPLETE")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()