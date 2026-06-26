import json
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"
ALL_GAMES_FILE = Path("data/processed/all_games.json")

HEADERS = [
    "Rank",
    "Game",
    "Team",
    "Player",
    "Likely",
    "Confidence",
    "Power",
    "Contact",
    "Pitcher",
    "Pitch Type",
    "Weather",
    "Park",
    "Recent",
    "Reasons",
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


def format_reasons(value):
    if isinstance(value, list):
        return ", ".join(value)
    return value or ""


def update_full_slate_hitters_sheet():
    games = load_json(ALL_GAMES_FILE)
    rows_data = []

    for game in games:
        for side in ["away", "home"]:
            team = game.get("away_team") if side == "away" else game.get("home_team")

            for hitter in game.get("hitters", {}).get(side, []):
                likely = hitter.get("Likely", "")

                if likely == "":
                    continue

                rows_data.append({
                    "game": game.get("game", ""),
                    "team": team,
                    "player": hitter.get("Player", ""),
                    "likely": likely,
                    "confidence": hitter.get("Confidence", ""),
                    "power": hitter.get("Power", ""),
                    "contact": hitter.get("Contact", ""),
                    "pitcher": hitter.get("Pitcher", ""),
                    "pitch_type": hitter.get("Pitch Type", ""),
                    "weather": hitter.get("Weather", ""),
                    "park": hitter.get("Park", ""),
                    "recent": hitter.get("Recent", ""),
                    "reasons": format_reasons(hitter.get("Reasons", "")),
                })

    rows_data.sort(key=lambda x: float(x["likely"] or 0), reverse=True)

    rows = [
        ["Alpha Wagerz Full Slate Hitters"],
        [],
        HEADERS,
    ]

    for i, item in enumerate(rows_data, start=1):
        rows.append([
            i,
            item["game"],
            item["team"],
            item["player"],
            item["likely"],
            item["confidence"],
            item["power"],
            item["contact"],
            item["pitcher"],
            item["pitch_type"],
            item["team"],
            item["weather"],
            item["park"],
            item["recent"],
            item["reasons"],
        ])

    client = get_client()
    sheet = client.open(SHEET_NAME)

    try:
        ws = sheet.worksheet("Full Slate Hitters")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="Full Slate Hitters", rows=500, cols=20)

    ws.clear()
    ws.update(rows)

    ws.format("A:N", {
        "textFormat": {"foregroundColor": {"red": 0, "green": 0, "blue": 0}},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    })

    ws.format("A1:N1", {
        "backgroundColor": {"red": 0.02, "green": 0.05, "blue": 0.10},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
            "fontSize": 14,
        },
    })

    ws.format("A3:N3", {
        "backgroundColor": {"red": 0.08, "green": 0.36, "blue": 0.48},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
        },
    })

    ws.format("E:M", {
        "numberFormat": {
            "type": "NUMBER",
            "pattern": "0.0",
        }
    })

    print("✅ Updated Full Slate Hitters sheet")


if __name__ == "__main__":
    update_full_slate_hitters_sheet()