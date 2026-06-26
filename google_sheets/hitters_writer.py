import gspread
from google.oauth2.service_account import Credentials
from model.dashboard import build_dashboard_payload

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"

HEADERS = [
    "Player", "Team", "Bats", "Opp Pitcher", "Throws",
    "Matchup", "Test Score", "Ceiling", "Zone Fit", "HR Form", "kHR",
    "Pitches", "BIP", "ISO", "xwOBA", "xwOBAcon", "SwStr%",
    "PulledBrl%", "Brl/BIP%", "Sweet Spot%", "FB%", "HH%", "LA", "Likely"
]


def get_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=scopes)
    return gspread.authorize(creds)


def hitter_section(title, hitters, team_name, opp_pitcher):
    rows = [[title], HEADERS]

    for hitter in hitters:
        rows.append([
            hitter.get("Player", ""),
            hitter.get("Team", team_name),
            hitter.get("Team Abbr", ""),
            hitter.get("Bats", ""),
            opp_pitcher,
            hitter.get("Throws", ""),
            hitter.get("Matchup", ""),
            hitter.get("Test Score", ""),
            hitter.get("Ceiling", ""),
            hitter.get("Zone Fit", ""),
            hitter.get("HR Form", ""),
            hitter.get("kHR", ""),
            hitter.get("Pitches", ""),
            hitter.get("BIP", ""),
            hitter.get("ISO", ""),
            hitter.get("xwOBA", ""),
            hitter.get("xwOBAcon", ""),
            hitter.get("SwStr%", ""),
            hitter.get("PulledBrl%", ""),
            hitter.get("Brl/BIP%", ""),
            hitter.get("Sweet Spot%", ""),
            hitter.get("FB%", ""),
            hitter.get("HH%", ""),
            hitter.get("LA", ""),
            hitter.get("Likely", ""),
        ])

    return rows


def apply_formatting(ws):
    # Reset readable text
    ws.format("A:Z", {
        "textFormat": {
            "foregroundColor": {"red": 0, "green": 0, "blue": 0},
            "fontSize": 10
        },
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE"
    })

    # Title rows / section rows
    ws.format("A1:Z1", {
        "backgroundColor": {"red": 0.02, "green": 0.05, "blue": 0.10},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
            "fontSize": 14
        }
    })

    # Headers
    ws.format("A4:Z4", {
        "backgroundColor": {"red": 0.08, "green": 0.36, "blue": 0.48},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True
        }
    })

    # Likely column as number, NOT percent
    ws.format("X:X", {
        "numberFormat": {
            "type": "NUMBER",
            "pattern": "0.0"
        }
    })


def update_hitter_matchups(game_id):
    payload = build_dashboard_payload(game_id)
    selected = payload["selected_game"]
    hitters = payload["hitters"]

    client = get_client()
    sheet = client.open(SHEET_NAME)
    ws = sheet.worksheet("Hitter Matchups")

    rows = [
        [f'Hitter Matchups — {selected["game"]}'],
        [],
    ]

    rows += hitter_section(
        f'{selected["away_team"]} Hitters',
        hitters.get("away", []),
        selected["away_team"],
        selected["home_sp"],
    )

    rows += [[]]

    rows += hitter_section(
        f'{selected["home_team"]} Hitters',
        hitters.get("home", []),
        selected["home_team"],
        selected["away_sp"],
    )

    ws.clear()
    ws.update(rows)
    apply_formatting(ws)

    print(f"✅ Updated Hitter Matchups for {selected['game']}")