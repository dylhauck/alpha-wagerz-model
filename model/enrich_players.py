import json
from pathlib import Path

GAMES_DIR = Path("data/processed/games")
PLAYER_REFERENCE_FILE = Path("data/processed/player_reference.json")


def load_json(filepath):
    if not filepath.exists():
        return [] if filepath == PLAYER_REFERENCE_FILE else {}

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def normalize_name(name):
    return str(name or "").strip().lower().replace(".", "").replace(",", "")


def build_player_lookup():
    players = load_json(PLAYER_REFERENCE_FILE)

    by_id = {}
    by_name = {}

    for player in players:
        player_id = player.get("player_id")
        name = normalize_name(player.get("player_name"))

        if player_id:
            by_id[str(player_id)] = player

        if name:
            by_name[name] = player

    return by_id, by_name


def find_player(player_obj, by_id, by_name):
    player_id = player_obj.get("Player ID") or player_obj.get("id")
    player_name = player_obj.get("Player") or player_obj.get("name")

    if player_id and str(player_id) in by_id:
        return by_id[str(player_id)]

    return by_name.get(normalize_name(player_name), {})


def enrich_hitter(hitter, by_id, by_name):
    ref = find_player(hitter, by_id, by_name)

    hitter["Team"] = hitter.get("Team") or ref.get("team_name", "")
    hitter["Team Abbr"] = hitter.get("Team Abbr") or ref.get("team_abbr", "")
    hitter["Bats"] = hitter.get("Bats") or ref.get("bats", "")
    hitter["Throws"] = hitter.get("Throws") or ref.get("throws", "")
    hitter["Position"] = hitter.get("Position") or ref.get("position", "")

    return hitter


def enrich_pitcher(pitcher, by_id, by_name):
    ref = by_name.get(normalize_name(pitcher.get("Pitcher", "")), {})

    pitcher["Throws"] = pitcher.get("Throws") or ref.get("throws", "")
    pitcher["Position"] = pitcher.get("Position") or ref.get("position", "")

    return pitcher


def get_game_hitters(game, side):
    hitters = game.get("hitters", {})

    if isinstance(hitters, dict):
        return hitters.get(side, [])

    if side == "away":
        return game.get("away_hitters", [])

    if side == "home":
        return game.get("home_hitters", [])

    return []

def enrich_players_in_games():
    by_id, by_name = build_player_lookup()

    updated = 0

    for file in GAMES_DIR.glob("*.json"):
        game = load_json(file)

        for side in ["away", "home"]:
            team = game.get("away_team") if side == "away" else game.get("home_team")
            team_abbr = ""

            for hitter in get_game_hitters(game, side):
                hitter["Team"] = team
                hitter["Team Abbr"] = team_abbr
                enrich_hitter(hitter, by_id, by_name)

        game["pitchers"] = [
            enrich_pitcher(pitcher, by_id, by_name)
            for pitcher in game.get("pitchers", [])
        ]

        save_json(game, file)
        updated += 1

    print(f"✅ Enriched players in {updated} game files")


if __name__ == "__main__":
    enrich_players_in_games()