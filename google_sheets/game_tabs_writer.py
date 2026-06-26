import gspread
from google.oauth2.service_account import Credentials

from config.team_assets import TEAM_ASSETS
from model.game_selector import get_game_index

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"

TARGET_TABS = [
    "Slate Summary",
    "Hitter Matchups",
    "Pitcher Slate",
    "Weather",
]


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)


def logo_formula(team_name):
    asset = TEAM_ASSETS.get(team_name)
    if not asset:
        return team_name

    return f'=IMAGE("{asset["logo"]}", 4, 34, 34)'


def build_game_tab_rows():
    games = get_game_index()

    logo_row = []
    time_row = []
    id_row = []

    for game in games:
        logo_row += [
            logo_formula(game["away_team"]),
            "@",
            logo_formula(game["home_team"]),
            "",
        ]

        time_row += [
            "",
            game.get("game_time", "") or game.get("status", ""),
            "",
            "",
        ]

        id_row += [
            "",
            game["game_id"],
            "",
            "",
        ]

    return [logo_row, time_row, id_row]


def write_game_tabs():
    client = get_client()
    sheet = client.open(SHEET_NAME)

    rows = build_game_tab_rows()

    for tab in TARGET_TABS:
        ws = sheet.worksheet(tab)

        ws.update("A1", rows)

        ws.format("A1:ZZ3", {
            "backgroundColor": {"red": 0.96, "green": 0.97, "blue": 0.99},
            "textFormat": {
                "foregroundColor": {"red": 0.05, "green": 0.05, "blue": 0.05},
                "bold": True,
                "fontSize": 10,
            },
            "horizontalAlignment": "CENTER",
            "verticalAlignment": "MIDDLE",
        })

        ws.format("A2:ZZ2", {
            "textFormat": {
                "foregroundColor": {"red": 0.25, "green": 0.25, "blue": 0.25},
                "fontSize": 8,
            },
        })

        ws.format("A3:ZZ3", {
            "textFormat": {
                "foregroundColor": {"red": 0.65, "green": 0.65, "blue": 0.65},
                "fontSize": 7,
            },
        })

        ws.freeze(rows=3)

    print("✅ Kasper-style game logo tabs added")


if __name__ == "__main__":
    write_game_tabs()