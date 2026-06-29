import gspread
from google.oauth2.service_account import Credentials

from model.dashboard import build_dashboard_payload

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"

HEADERS = [
    "Player",
    "Team",
    "Power Score",
    "Contact Score",
    "Pitcher Matchup",
    "Pitch Type",
    "Team Offense",
    "Bullpen",
    "Weather Impact",
    "Park Factor",
    "Recent Form",
    "Likely",
    "Confidence",
    "Reasons",
]


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)


def format_reasons(value):
    if isinstance(value, list):
        return ", ".join(value)
    return value or ""


def update_model_breakdown(game_id):
    payload = build_dashboard_payload(game_id)

    hitters = payload["hitters"]
    selected = payload["selected_game"]

    client = get_client()
    sheet = client.open(SHEET_NAME)
    ws = sheet.worksheet("Model Breakdown")

    rows = [
        [f"Alpha Model Breakdown — {selected['game']}"],
        [],
        HEADERS,
    ]

    for side in ["away", "home"]:
        team = selected["away_team"] if side == "away" else selected["home_team"]

        for hitter in hitters.get(side, []):
            rows.append([
                hitter.get("Player", ""),
                team,
                hitter.get("Power", ""),
                hitter.get("Contact", ""),
                hitter.get("Pitcher", ""),
                hitter.get("Pitch Type", ""),
                hitter.get("Team", ""),
                hitter.get("Bullpen", ""),
                hitter.get("Weather", ""),
                hitter.get("Park", ""),
                hitter.get("Recent", ""),
                hitter.get("Likely", ""),
                hitter.get("Confidence", ""),
                format_reasons(hitter.get("Reasons", "")),
            ])

    ws.clear()
    ws.update(rows)

    ws.format("A:N", {
        "textFormat": {
            "foregroundColor": {"red": 0, "green": 0, "blue": 0}
        },
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

    ws.format("C:M", {
        "numberFormat": {
            "type": "NUMBER",
            "pattern": "0.0",
        }
    })

    print("✅ Updated Model Breakdown")