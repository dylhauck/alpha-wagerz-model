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
    "Pitcher",
    "Opponent",
    "Pitch Score",
    "Strikeout Score",
    "xwOBA",
    "CSW%",
    "SwStr%",
    "Ball%",
    "Brl/BIP%",
    "FB%",
    "HH%",
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


def safe_score(value):
    try:
        return float(value)
    except:
        return 0


def update_full_slate_pitchers_sheet():
    games = load_json(ALL_GAMES_FILE)
    rows_data = []

    for game in games:
        for pitcher in game.get("pitchers", []):
            rows_data.append({
                "game": game.get("game", ""),
                "team": pitcher.get("Team", ""),
                "pitcher": pitcher.get("Pitcher", ""),
                "opponent": pitcher.get("Opponent", ""),
                "pitch_score": pitcher.get("Pitch Score", ""),
                "strikeout_score": pitcher.get("Strikeout Score", ""),
                "xwoba": pitcher.get("xwOBA", ""),
                "csw": pitcher.get("CSW%", ""),
                "swstr": pitcher.get("SwStr%", ""),
                "ball": pitcher.get("Ball%", ""),
                "brl": pitcher.get("Brl/BIP%", ""),
                "fb": pitcher.get("FB%", ""),
                "hh": pitcher.get("HH%", ""),
            })

    rows_data.sort(key=lambda x: safe_score(x["strikeout_score"]), reverse=True)

    rows = [
        ["Alpha Wagerz Full Slate Pitchers"],
        [],
        HEADERS,
    ]

    for i, item in enumerate(rows_data, start=1):
        rows.append([
            i,
            item["game"],
            item["team"],
            item["pitcher"],
            item["opponent"],
            item["pitch_score"],
            item["strikeout_score"],
            item["xwoba"],
            item["csw"],
            item["swstr"],
            item["ball"],
            item["brl"],
            item["fb"],
            item["hh"],
        ])

    client = get_client()
    sheet = client.open(SHEET_NAME)

    try:
        ws = sheet.worksheet("Full Slate Pitchers")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="Full Slate Pitchers", rows=100, cols=20)

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

    ws.format("F:N", {
        "numberFormat": {
            "type": "NUMBER",
            "pattern": "0.0",
        }
    })

    print("✅ Updated Full Slate Pitchers sheet")


if __name__ == "__main__":
    update_full_slate_pitchers_sheet()