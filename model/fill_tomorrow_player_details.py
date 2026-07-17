from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests

from utils.json_utils import load_json, save_json


GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)

PLAYER_REFERENCE_FILE = Path(
    "data/processed/player_reference.json"
)

MLB_PEOPLE_URL = (
    "https://statsapi.mlb.com/api/v1/people"
)

REQUEST_TIMEOUT = 30


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def clean_id(value: Any) -> str:
    value = clean_text(value)

    # A valid MLB player ID should be numeric.
    return value if value.isdigit() else ""


def normalize_name(value: Any) -> str:
    return (
        clean_text(value)
        .lower()
        .replace(".", "")
        .replace(",", "")
        .replace("'", "")
        .replace("-", " ")
    )


def load_player_reference() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    players = load_json(
        PLAYER_REFERENCE_FILE,
        default=[],
    )

    if not isinstance(players, list):
        players = []

    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}

    for player in players:
        if not isinstance(player, dict):
            continue

        player_id = clean_id(
            player.get("player_id")
            or player.get("id")
        )

        player_name = normalize_name(
            player.get("player_name")
            or player.get("name")
        )

        if player_id:
            by_id[player_id] = player

        if player_name:
            by_name[player_name] = player

    print(
        f"📚 Loaded {len(by_id)} player IDs and "
        f"{len(by_name)} player names from reference"
    )

    return by_id, by_name


def player_name_from_row(
    row: dict[str, Any],
    player_type: str,
) -> str:
    if player_type == "pitcher":
        return clean_text(
            row.get("Pitcher")
            or row.get("player_name")
            or row.get("name")
        )

    return clean_text(
        row.get("Player")
        or row.get("player_name")
        or row.get("name")
    )


def player_id_from_row(
    row: dict[str, Any],
    player_type: str,
) -> str:
    if player_type == "pitcher":
        candidates = [
            row.get("pitcher_id"),
            row.get("player_id"),
            row.get("id"),
            row.get("Pitcher ID"),
        ]
    else:
        candidates = [
            row.get("player_id"),
            row.get("id"),
            row.get("Player ID"),
        ]

    for candidate in candidates:
        player_id = clean_id(candidate)

        if player_id:
            return player_id

    return ""


def find_reference_player(
    row: dict[str, Any],
    player_type: str,
    by_id: dict[str, dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    player_id = player_id_from_row(
        row,
        player_type,
    )

    if player_id and player_id in by_id:
        return by_id[player_id]

    player_name = normalize_name(
        player_name_from_row(
            row,
            player_type,
        )
    )

    return by_name.get(
        player_name,
        {},
    )


def get_hitter_lists(
    game: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    hitters = game.get("hitters")

    if isinstance(hitters, dict):
        away = hitters.get("away", [])
        home = hitters.get("home", [])
    else:
        away = game.get(
            "away_hitters",
            [],
        )
        home = game.get(
            "home_hitters",
            [],
        )

    if not isinstance(away, list):
        away = []

    if not isinstance(home, list):
        home = []

    return away, home


def update_hitter_from_reference(
    hitter: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
    game_name: str,
) -> dict[str, Any]:
    updated = dict(hitter)

    reference = find_reference_player(
        updated,
        "hitter",
        by_id,
        by_name,
    )

    bats = (
        clean_text(updated.get("Bats"))
        or clean_text(updated.get("bats"))
        or clean_text(reference.get("bats"))
        or clean_text(reference.get("bat_side"))
    )

    throws = (
        clean_text(updated.get("Throws"))
        or clean_text(updated.get("throws"))
        or clean_text(reference.get("throws"))
        or clean_text(reference.get("throw_side"))
    )

    position = (
        clean_text(updated.get("Position"))
        or clean_text(updated.get("position"))
        or clean_text(reference.get("position"))
    )

    player_id = (
        player_id_from_row(
            updated,
            "hitter",
        )
        or clean_id(
            reference.get("player_id")
            or reference.get("id")
        )
    )

    updated["Bats"] = bats
    updated["bats"] = bats

    updated["Throws"] = throws
    updated["throws"] = throws

    updated["Position"] = position
    updated["position"] = position

    updated["Game"] = game_name
    updated["game"] = game_name

    if player_id:
        updated["Player ID"] = player_id
        updated["player_id"] = player_id
        updated["id"] = player_id

    return updated


def update_pitcher_from_reference(
    pitcher: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    by_name: dict[str, dict[str, Any]],
    game_name: str,
) -> dict[str, Any]:
    updated = dict(pitcher)

    reference = find_reference_player(
        updated,
        "pitcher",
        by_id,
        by_name,
    )

    throws = (
        clean_text(updated.get("Throws"))
        or clean_text(updated.get("throws"))
        or clean_text(reference.get("throws"))
        or clean_text(reference.get("throw_side"))
    )

    position = (
        clean_text(updated.get("Position"))
        or clean_text(updated.get("position"))
        or clean_text(reference.get("position"))
        or "SP"
    )

    pitcher_id = (
        player_id_from_row(
            updated,
            "pitcher",
        )
        or clean_id(
            reference.get("player_id")
            or reference.get("id")
        )
    )

    updated["Throws"] = throws
    updated["throws"] = throws

    updated["Position"] = position
    updated["position"] = position

    # Force the matchup into every field the web table
    # might use.
    updated["Game"] = game_name
    updated["game"] = game_name
    updated["Matchup"] = game_name

    if pitcher_id:
        updated["Pitcher ID"] = pitcher_id
        updated["pitcher_id"] = pitcher_id
        updated["player_id"] = pitcher_id
        updated["id"] = pitcher_id

    return updated


def fetch_missing_people(
    missing_ids: set[str],
) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}

    ids = sorted(
        player_id
        for player_id in missing_ids
        if player_id.isdigit()
    )

    for start in range(0, len(ids), 100):
        chunk = ids[start:start + 100]

        response = requests.get(
            MLB_PEOPLE_URL,
            params={
                "personIds": ",".join(chunk),
            },
            timeout=REQUEST_TIMEOUT,
            headers={
                "Accept": "application/json",
                "User-Agent": "Alpha-Wagerz/1.0",
            },
        )

        response.raise_for_status()

        payload = response.json()

        for person in payload.get(
            "people",
            [],
        ):
            player_id = clean_id(
                person.get("id")
            )

            if not player_id:
                continue

            lookup[player_id] = {
                "player_id": player_id,
                "player_name": clean_text(
                    person.get("fullName")
                ),
                "bats": clean_text(
                    (
                        person.get("batSide", {})
                        or {}
                    ).get("code")
                ),
                "throws": clean_text(
                    (
                        person.get("pitchHand", {})
                        or {}
                    ).get("code")
                ),
                "position": clean_text(
                    (
                        person.get(
                            "primaryPosition",
                            {},
                        )
                        or {}
                    ).get("abbreviation")
                ),
            }

    return lookup


def fill_tomorrow_player_details() -> int:
    if not GAMES_DIR.exists():
        raise FileNotFoundError(
            f"Tomorrow games folder was not found: "
            f"{GAMES_DIR}"
        )

    by_id, by_name = (
        load_player_reference()
    )

    # Collect IDs that are not already in the local reference.
    missing_ids: set[str] = set()

    for game_file in GAMES_DIR.glob(
        "*.json"
    ):
        game = load_json(
            game_file,
            default={},
        )

        if not isinstance(game, dict):
            continue

        away_hitters, home_hitters = (
            get_hitter_lists(game)
        )

        for hitter in (
            away_hitters
            + home_hitters
        ):
            if not isinstance(hitter, dict):
                continue

            player_id = player_id_from_row(
                hitter,
                "hitter",
            )

            if (
                player_id
                and player_id not in by_id
            ):
                missing_ids.add(player_id)

        pitchers = game.get(
            "pitchers",
            [],
        )

        if not isinstance(pitchers, list):
            pitchers = []

        for pitcher in pitchers:
            if not isinstance(pitcher, dict):
                continue

            player_id = player_id_from_row(
                pitcher,
                "pitcher",
            )

            if (
                player_id
                and player_id not in by_id
            ):
                missing_ids.add(player_id)

    if missing_ids:
        print(
            f"🌐 Fetching {len(missing_ids)} "
            f"missing MLB player records"
        )

        api_lookup = fetch_missing_people(
            missing_ids
        )

        for player_id, player in (
            api_lookup.items()
        ):
            by_id[player_id] = player

            player_name = normalize_name(
                player.get("player_name")
            )

            if player_name:
                by_name[player_name] = player

    updated_games = 0

    for game_file in GAMES_DIR.glob(
        "*.json"
    ):
        game = load_json(
            game_file,
            default={},
        )

        if not isinstance(game, dict) or not game:
            continue

        game_name = clean_text(
            game.get("game")
        )

        away_hitters, home_hitters = (
            get_hitter_lists(game)
        )

        away_hitters = [
            update_hitter_from_reference(
                hitter,
                by_id,
                by_name,
                game_name,
            )
            for hitter in away_hitters
            if isinstance(hitter, dict)
        ]

        home_hitters = [
            update_hitter_from_reference(
                hitter,
                by_id,
                by_name,
                game_name,
            )
            for hitter in home_hitters
            if isinstance(hitter, dict)
        ]

        pitchers = game.get(
            "pitchers",
            [],
        )

        if not isinstance(pitchers, list):
            pitchers = []

        pitchers = [
            update_pitcher_from_reference(
                pitcher,
                by_id,
                by_name,
                game_name,
            )
            for pitcher in pitchers
            if isinstance(pitcher, dict)
        ]

        game["away_hitters"] = (
            away_hitters
        )

        game["home_hitters"] = (
            home_hitters
        )

        game["hitters"] = {
            "away": away_hitters,
            "home": home_hitters,
        }

        game["pitchers"] = pitchers

        game["away_pitcher"] = (
            pitchers[0]
            if len(pitchers) > 0
            else {}
        )

        game["home_pitcher"] = (
            pitchers[1]
            if len(pitchers) > 1
            else {}
        )

        save_json(
            game,
            game_file,
        )

        hitter_hands = sum(
            1
            for hitter in (
                away_hitters
                + home_hitters
            )
            if hitter.get("Bats")
        )

        pitcher_hands = sum(
            1
            for pitcher in pitchers
            if pitcher.get("Throws")
        )

        print(
            f"✅ {game_name} | "
            f"hitter hands: {hitter_hands}/"
            f"{len(away_hitters) + len(home_hitters)} | "
            f"pitcher hands: {pitcher_hands}/"
            f"{len(pitchers)}"
        )

        updated_games += 1

    print()
    print(
        f"✅ Filled tomorrow handedness and "
        f"pitcher game labels for "
        f"{updated_games} games"
    )

    return updated_games


if __name__ == "__main__":
    fill_tomorrow_player_details()