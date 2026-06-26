import json
from pathlib import Path

from model.dashboard import build_dashboard_payload
from model.dashboard_layout import build_dashboard_rows


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    game_index = load_json("data/processed/game_index.json")
    game_tabs = [game["game"] for game in game_index]

    game_id = input("Enter game_id: ").strip()
    payload = build_dashboard_payload(game_id)

    rows = build_dashboard_rows(payload, game_tabs)

    for row in rows:
        print(row)


if __name__ == "__main__":
    main()