import gspread
from google.oauth2.service_account import Credentials

from model.dashboard import build_dashboard_payload
from model.dashboard_layout import build_dashboard_rows
from model.game_selector import get_game_index

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)


def update_selected_game_dashboard(game_id):
    payload = build_dashboard_payload(game_id)
    game_tabs = [game["game"] for game in get_game_index()]
    rows = build_dashboard_rows(payload, game_tabs)

    client = get_client()
    sheet = client.open(SHEET_NAME)
    worksheet = sheet.worksheet("Slate Summary")

    worksheet.clear()
    worksheet.update(rows)

    print(f"✅ Updated Dashboard for {payload['selected_game']['game']}")