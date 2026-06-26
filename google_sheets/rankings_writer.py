import json
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"
RANKINGS_FILE = Path("data/processed/rankings.json")

HEADERS = ["Rank", "Category", "Player/Team", "Game", "Score", "Notes"]


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


def update_rankings_sheet():
    rankings = load_json(RANKINGS_FILE)

    rows = [
        ["Alpha Wagerz Rankings"],
        [],
        ["Top HR Targets"],
        HEADERS,
    ]

    for i, item in enumerate(rankings.get("hr_targets", []), start=1):
        rows.append([
            i,
            item["Category"],
            item["Player/Team"],
            item["Game"],
            item["Score"],
            item["Notes"],
        ])

    rows += [
        [],
        ["Top Pitcher K Targets"],
        HEADERS,
    ]

    for i, item in enumerate(rankings.get("pitchers", []), start=1):
        rows.append([
            i,
            item["Category"],
            item["Player/Team"],
            item["Game"],
            item["Score"],
            item["Notes"],
        ])

    client = get_client()
    sheet = client.open(SHEET_NAME)
    ws = sheet.worksheet("Rankings")

    ws.clear()
    ws.update(rows)

    ws.format("A:Z", {
        "textFormat": {"foregroundColor": {"red": 0, "green": 0, "blue": 0}},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    })

    ws.format("A1:Z1", {
        "backgroundColor": {"red": 0.02, "green": 0.05, "blue": 0.10},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
            "fontSize": 14,
        },
    })

    print("✅ Updated Rankings sheet")


if __name__ == "__main__":
    update_rankings_sheet()