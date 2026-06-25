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

    creds = Credentials.from_service_account_file(
        CREDENTIALS_FILE,
        scopes=scopes,
    )

    return gspread.authorize(creds)


def update_selected_game_dashboard(game_id):
    payload = build_dashboard_payload(game_id)

    client = get_client()
    sheet = client.open(SHEET_NAME)

    worksheet = sheet.worksheet("Slate Summary")
    worksheet.clear()

    selected = payload["selected_game"]

    rows = [
        ["Alpha Wagerz Selected Game Dashboard"],
        [],
        ["Game", selected["game"]],
        ["Venue", selected["venue"]],
        ["Away SP", selected["away_sp"]],
        ["Home SP", selected["home_sp"]],
        ["Status", selected["status"]],
        [],
        ["Top HR Target", payload["slate_summary"].get("top_hr_target", "")],
        ["Top Pitcher", payload["slate_summary"].get("top_pitcher", "")],
        ["Alpha Game Rating", payload["slate_summary"].get("alpha_game_rating", "")],
        ["Notes", payload["slate_summary"].get("notes", "")],
    ]

    worksheet.update(rows)

    print(f"✅ Updated Slate Summary for {selected['game']}")