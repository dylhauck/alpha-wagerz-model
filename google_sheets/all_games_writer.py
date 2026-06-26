import json
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"
ALL_GAMES_FILE = Path("data/processed/all_games.json")

HEADERS = [
    "Game ID",
    "Game",
    "Venue",
    "Away Team",
    "Home Team",
    "Away SP",
    "Home SP",
    "Status",
    "Lineup Status",
    "Temperature",
    "Humidity",
    "Conditions",
    "Wind Direction",
    "Wind Speed",
    "Away Hitters",
    "Home Hitters",
]


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)


def load_json(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def hitter_count(game, side):
    return len(game.get("hitters", {}).get(side, []))


def update_all_games_sheet():
    games = load_json(ALL_GAMES_FILE)

    rows = [
        ["Alpha Wagerz Full Slate"],
        [],
        HEADERS,
    ]

    for game in games:
        weather = game.get("weather", {})

        rows.append([
            game.get("game_id", ""),
            game.get("game", ""),
            game.get("venue", ""),
            game.get("away_team", ""),
            game.get("home_team", ""),
            game.get("away_sp", ""),
            game.get("home_sp", ""),
            game.get("status", ""),
            game.get("lineup_status", ""),
            weather.get("temperature", game.get("temperature", "")),
            weather.get("humidity", game.get("humidity", "")),
            weather.get("conditions", game.get("conditions", "")),
            weather.get("wind_direction", game.get("wind_direction", "")),
            weather.get("wind_speed", game.get("wind_speed", "")),
            hitter_count(game, "away"),
            hitter_count(game, "home"),
        ])

    client = get_client()
    sheet = client.open(SHEET_NAME)

    try:
        ws = sheet.worksheet("Full Slate")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="Full Slate", rows=100, cols=30)

    ws.clear()
    ws.update(rows)

    ws.format("A:P", {
        "textFormat": {"foregroundColor": {"red": 0, "green": 0, "blue": 0}},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    })

    ws.format("A1:P1", {
        "backgroundColor": {"red": 0.02, "green": 0.05, "blue": 0.10},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
            "fontSize": 14,
        },
    })

    ws.format("A3:P3", {
        "backgroundColor": {"red": 0.08, "green": 0.36, "blue": 0.48},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
        },
    })

    print("✅ Updated Full Slate sheet")


if __name__ == "__main__":
    update_all_games_sheet()