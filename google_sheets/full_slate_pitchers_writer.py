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
    "HR Vulnerability",
    "Fly Ball Profile",
    "Barrel Profile",
    "Pitches",
    "BF",
    "IP",
    "HR",
    "K",
    "BB",
    "xwOBA",
    "xwOBAcon",
    "CSW%",
    "SwStr%",
    "Ball%",
    "PulledBrl%",
    "Brl/BIP%",
    "FB%",
    "GB%",
    "HH%",
    "K%",
    "BB%",
    "HR/9",
    "AvgEV",
    "AvgLA",
    "FBv",
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
    except Exception:
        return 0


def update_full_slate_pitchers_sheet():
    games = load_json(ALL_GAMES_FILE)
    rows_data = []

    for game in games:
        for pitcher in game.get("pitchers", []):
            rows_data.append({
                header: pitcher.get(header, "")
                for header in HEADERS
                if header not in ["Rank", "Game"]
            } | {"Game": game.get("game", "")})

    rows_data.sort(key=lambda x: safe_score(x.get("Strikeout Score", "")), reverse=True)

    rows = [
        ["Alpha Wagerz Full Slate Pitchers"],
        [],
        HEADERS,
    ]

    for i, item in enumerate(rows_data, start=1):
        rows.append([
            i,
            item.get("Game", ""),
            item.get("Team", ""),
            item.get("Pitcher", ""),
            item.get("Opponent", ""),
            item.get("Pitch Score", ""),
            item.get("Strikeout Score", ""),
            item.get("HR Vulnerability", ""),
            item.get("Fly Ball Profile", ""),
            item.get("Barrel Profile", ""),
            item.get("Pitches", ""),
            item.get("BF", ""),
            item.get("IP", ""),
            item.get("HR", ""),
            item.get("K", ""),
            item.get("BB", ""),
            item.get("xwOBA", ""),
            item.get("xwOBAcon", ""),
            item.get("CSW%", ""),
            item.get("SwStr%", ""),
            item.get("Ball%", ""),
            item.get("PulledBrl%", ""),
            item.get("Brl/BIP%", ""),
            item.get("FB%", ""),
            item.get("GB%", ""),
            item.get("HH%", ""),
            item.get("K%", ""),
            item.get("BB%", ""),
            item.get("HR/9", ""),
            item.get("AvgEV", ""),
            item.get("AvgLA", ""),
            item.get("FBv", ""),
        ])

    client = get_client()
    sheet = client.open(SHEET_NAME)

    try:
        ws = sheet.worksheet("Full Slate Pitchers")
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title="Full Slate Pitchers", rows=100, cols=40)

    ws.clear()
    ws.update(rows)

    ws.format("A:AF", {
        "textFormat": {"foregroundColor": {"red": 0, "green": 0, "blue": 0}},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    })

    ws.format("A1:AF1", {
        "backgroundColor": {"red": 0.02, "green": 0.05, "blue": 0.10},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
            "fontSize": 14,
        },
    })

    ws.format("A3:AF3", {
        "backgroundColor": {"red": 0.08, "green": 0.36, "blue": 0.48},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
        },
    })

    ws.format("F:AF", {
        "numberFormat": {
            "type": "NUMBER",
            "pattern": "0.0",
        }
    })

    print("✅ Updated Full Slate Pitchers sheet")


if __name__ == "__main__":
    update_full_slate_pitchers_sheet()