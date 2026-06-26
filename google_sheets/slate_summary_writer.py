import gspread
from google.oauth2.service_account import Credentials

from model.dashboard import build_dashboard_payload

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)


def update_slate_summary(game_id):
    payload = build_dashboard_payload(game_id)
    selected = payload["selected_game"]
    weather = payload.get("weather", {})
    summary = payload.get("slate_summary", {})

    rows = [
        ["ALPHA WAGERZ SLATE SUMMARY"],
        [],
        ["Selected Game", selected.get("game", "")],
        ["Venue", selected.get("venue", "")],
        ["Away SP", selected.get("away_sp", "")],
        ["Home SP", selected.get("home_sp", "")],
        ["Lineup Status", selected.get("lineup_status", "")],
        [],
        ["Weather"],
        ["Temperature", weather.get("temperature", "")],
        ["Humidity", weather.get("humidity", "")],
        ["Conditions", weather.get("conditions", "")],
        ["Wind", f'{weather.get("wind_direction", "")} {weather.get("wind_speed", "")} MPH'],
        [],
        ["Alpha Predictions"],
        ["Moneyline Lean", summary.get("moneyline_lean", "")],
        ["Run Line Lean", summary.get("spread_lean", "")],
        ["Over/Under Lean", summary.get("total_lean", "")],
        ["Projected Score", summary.get("projected_score", "")],
        ["Confidence", summary.get("confidence_score", "")],
    ]

    client = get_client()
    sheet = client.open(SHEET_NAME)
    ws = sheet.worksheet("Slate Summary")

    ws.clear()
    ws.update(rows)

    ws.format("A:B", {
        "textFormat": {"foregroundColor": {"red": 0, "green": 0, "blue": 0}},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    })

    ws.format("A1:B1", {
        "backgroundColor": {"red": 0.02, "green": 0.05, "blue": 0.10},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
            "fontSize": 14,
        },
    })

    print(f"✅ Updated Slate Summary for {selected['game']}")