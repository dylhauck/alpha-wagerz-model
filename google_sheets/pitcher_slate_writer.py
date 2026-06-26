import gspread
from google.oauth2.service_account import Credentials
from model.dashboard import build_dashboard_payload

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"

HEADERS = [
    "Team",
    "Pitcher",
    "Throws",
    "Opponent",
    "Pitch Score",
    "Strikeout Score",
    "xwOBA",
    "CSW%",
    "SwStr%",
    "Ball%",
    "PulledBrl%",
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


def update_pitcher_slate(game_id):
    payload = build_dashboard_payload(game_id)
    selected = payload["selected_game"]
    pitchers = payload.get("pitchers", [])

    client = get_client()
    sheet = client.open(SHEET_NAME)
    ws = sheet.worksheet("Pitcher Slate")

    rows = [
        [f'Pitcher Slate — {selected["game"]}'],
        [],
        HEADERS,
    ]

    for pitcher in pitchers:
        rows.append([pitcher.get(header, "") for header in HEADERS])

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

    ws.format("A3:Z3", {
        "backgroundColor": {"red": 0.08, "green": 0.36, "blue": 0.48},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
        },
    })

    print(f"✅ Updated Pitcher Slate for {selected['game']}")