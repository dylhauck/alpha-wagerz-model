import json
from pathlib import Path


GAMES_DIR = Path(
    "data/tomorrow/processed/games"
)

PLAYER_REFERENCE_FILE = Path(
    "data/processed/player_reference.json"
)


def load_json(filepath):
    if not filepath.exists():
        return (
            []
            if filepath == PLAYER_REFERENCE_FILE
            else {}
        )

    with filepath.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_json(
    data,
    filepath,
):
    filepath.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with filepath.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def normalize_name(name):
    return (
        str(name or "")
        .strip()
        .lower()
        .replace(".", "")
        .replace(",", "")
    )


def build_player_lookup():
    players = load_json(
        PLAYER_REFERENCE_FILE
    )

    by_id = {}
    by_name = {}

    for player in players:
        player_id = player.get(
            "player_id"
        )

        name = normalize_name(
            player.get("player_name")
        )

        if player_id:
            by_id[str(player_id)] = player

        if name:
            by_name[name] = player

    return by_id, by_name


def find_player(
    player_obj,
    by_id,
    by_name,
):
    player_id = (
        player_obj.get("Player ID")
        or player_obj.get("player_id")
        or player_obj.get("id")
    )

    player_name = (
        player_obj.get("Player")
        or player_obj.get("Pitcher")
        or player_obj.get("name")
    )

    if (
        player_id
        and str(player_id) in by_id
    ):
        return by_id[str(player_id)]

    return by_name.get(
        normalize_name(player_name),
        {},
    )


def enrich_hitter(
    hitter,
    by_id,
    by_name,
):
    ref = find_player(
        hitter,
        by_id,
        by_name,
    )

    hitter["Team"] = (
        hitter.get("Team")
        or ref.get("team_name", "")
    )

    hitter["Team Abbr"] = (
        hitter.get("Team Abbr")
        or ref.get("team_abbr", "")
    )

    hitter["Bats"] = (
        hitter.get("Bats")
        or hitter.get("bats")
        or ref.get("bats", "")
    )

    hitter["bats"] = hitter["Bats"]

    hitter["Throws"] = (
        hitter.get("Throws")
        or hitter.get("throws")
        or ref.get("throws", "")
    )

    hitter["throws"] = hitter["Throws"]

    hitter["Position"] = (
        hitter.get("Position")
        or hitter.get("position")
        or ref.get("position", "")
    )

    hitter["position"] = (
        hitter["Position"]
    )

    return hitter


def enrich_pitcher(
    pitcher,
    by_id,
    by_name,
):
    ref = find_player(
        pitcher,
        by_id,
        by_name,
    )

    pitcher["Throws"] = (
        pitcher.get("Throws")
        or pitcher.get("throws")
        or ref.get("throws", "")
    )

    pitcher["throws"] = (
        pitcher["Throws"]
    )

    pitcher["Position"] = (
        pitcher.get("Position")
        or pitcher.get("position")
        or ref.get("position", "")
    )

    pitcher["position"] = (
        pitcher["Position"]
    )

    return pitcher


def get_game_hitters(
    game,
    side,
):
    hitters = game.get(
        "hitters",
        {},
    )

    if isinstance(
        hitters,
        dict,
    ):
        return hitters.get(
            side,
            [],
        )

    if side == "away":
        return game.get(
            "away_hitters",
            [],
        )

    if side == "home":
        return game.get(
            "home_hitters",
            [],
        )

    return []


def enrich_tomorrow_players_in_games():
    by_id, by_name = (
        build_player_lookup()
    )

    updated = 0

    for file in GAMES_DIR.glob(
        "*.json"
    ):
        game = load_json(file)

        if not isinstance(
            game,
            dict,
        ):
            continue

        away_hitters = (
            get_game_hitters(
                game,
                "away",
            )
        )

        home_hitters = (
            get_game_hitters(
                game,
                "home",
            )
        )

        away_team = game.get(
            "away_team",
            "",
        )

        home_team = game.get(
            "home_team",
            "",
        )

        for hitter in away_hitters:
            if not isinstance(
                hitter,
                dict,
            ):
                continue

            hitter["Team"] = (
                hitter.get("Team")
                or away_team
            )

            enrich_hitter(
                hitter,
                by_id,
                by_name,
            )

        for hitter in home_hitters:
            if not isinstance(
                hitter,
                dict,
            ):
                continue

            hitter["Team"] = (
                hitter.get("Team")
                or home_team
            )

            enrich_hitter(
                hitter,
                by_id,
                by_name,
            )

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

        pitchers = game.get(
            "pitchers",
            [],
        )

        if not isinstance(
            pitchers,
            list,
        ):
            pitchers = []

        game_name = game.get(
            "game",
            "",
        )

        enriched_pitchers = []

        for pitcher in pitchers:
            if not isinstance(
                pitcher,
                dict,
            ):
                continue

            enrich_pitcher(
                pitcher,
                by_id,
                by_name,
            )

            pitcher["Game"] = (
                pitcher.get("Game")
                or game_name
            )

            enriched_pitchers.append(
                pitcher
            )

        game["pitchers"] = (
            enriched_pitchers
        )

        game["away_pitcher"] = (
            enriched_pitchers[0]
            if len(enriched_pitchers) > 0
            else {}
        )

        game["home_pitcher"] = (
            enriched_pitchers[1]
            if len(enriched_pitchers) > 1
            else {}
        )

        save_json(
            game,
            file,
        )

        updated += 1

    print(
        f"✅ Enriched tomorrow players "
        f"in {updated} game files"
    )


if __name__ == "__main__":
    enrich_tomorrow_players_in_games()