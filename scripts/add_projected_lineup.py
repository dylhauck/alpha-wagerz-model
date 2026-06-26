import json
from pathlib import Path


PROJECTED_FILE = Path("data/manual/projected_lineups.json")


def load_json(filepath):
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(data, filepath):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def split_hitters(raw):
    return [name.strip() for name in raw.split(",") if name.strip()]


def main():
    projected = load_json(PROJECTED_FILE)

    game_id = input("Game ID: ").strip()
    game = input("Game name, ex KC @ TB: ").strip()

    away_hitters = split_hitters(input("Away hitters, comma separated: "))
    home_hitters = split_hitters(input("Home hitters, comma separated: "))

    projected[game_id] = {
        "game": game,
        "lineup_status": "projected",
        "away_hitters": away_hitters,
        "home_hitters": home_hitters,
    }

    save_json(projected, PROJECTED_FILE)

    print(f"✅ Saved projected lineup for {game}")


if __name__ == "__main__":
    main()