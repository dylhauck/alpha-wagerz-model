import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"

TABS = [
    "Slate Summary",
    "Hitter Matchups",
    "Pitcher Slate",
    "Weather",
    "Rankings",
    "Model Breakdown",
    "Model History",
    "Config",
]

HITTER_HEADERS = [
    "Player",
    "Team",
    "Bats",
    "Opp Pitcher",
    "Throws",
    "Matchup",
    "Test Score",
    "Ceiling",
    "Zone Fit",
    "HR Form",
    "kHR",
    "Pitches",
    "BIP",
    "ISO",
    "xwOBA",
    "xwOBAcon",
    "SwStr%",
    "PulledBrl%",
    "Brl/BIP%",
    "Sweet Spot%",
    "FB%",
    "HH%",
    "LA",
    "Likely",
]

PITCHER_HEADERS = [
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

WEATHER_HEADERS = [
    "Game",
    "Stadium",
    "Temperature",
    "Humidity",
    "Conditions",
    "Wind Direction",
    "Wind Speed",
    "Field Direction",
    "HR Impact",
    "Weather Score",
    "Notes",
]

RANKINGS_HEADERS = [
    "Rank",
    "Category",
    "Player/Team",
    "Game",
    "Score",
    "Notes",
]

MODEL_BREAKDOWN_HEADERS = [
    "Player",
    "Team",
    "Power Score",
    "Contact Score",
    "Pitcher Matchup",
    "Weather Impact",
    "Park Factor",
    "Recent Form",
    "Likely",
]

HISTORY_HEADERS = [
    "Date",
    "Game",
    "Pick Type",
    "Player/Team",
    "Prediction",
    "Score",
    "Result",
    "Hit?",
    "Notes",
]

CONFIG_ROWS = [
    ["Category", "Weight", "Enabled?", "Notes"],
    ["Power Metrics", 30, "Yes", ""],
    ["Pitcher Matchup", 25, "Yes", ""],
    ["Recent Form", 20, "Yes", ""],
    ["Weather", 15, "Yes", ""],
    ["Volume / Sample", 10, "Yes", ""],
]


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


def get_or_create_worksheet(sheet, title, rows=200, cols=40):
    try:
        return sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=title, rows=rows, cols=cols)


def setup_workbook():
    client = get_client()
    sheet = client.open(SHEET_NAME)

    for tab in TABS:
        get_or_create_worksheet(sheet, tab)

    #
    # SLATE SUMMARY
    #
    ws = sheet.worksheet("Slate Summary")
    ws.clear()

    ws.update([
        ["ALPHA WAGERZ MLB MODEL"],
        [],
        ["GAME TABS"],
        [],
        ["SELECTED GAME SUMMARY"],
        ["Game", ""],
        ["Venue", ""],
        ["Weather", ""],
        ["Wind", ""],
        ["Away SP", ""],
        ["Home SP", ""],
        ["Lineup Status", ""],
        [],
        ["ALPHA GAME PREDICTIONS"],
        ["Moneyline Lean", ""],
        ["Run Line Lean", ""],
        ["Over / Under Lean", ""],
        ["Projected Score", ""],
        ["Confidence", ""],
        [],
        ["GAME ENVIRONMENT"],
        ["Weather Boost", ""],
        ["Park Factor", ""],
        ["Offensive Rating", ""],
        ["Pitching Rating", ""],
        ["Bullpen Rating", ""],
        [],
        ["KEY NOTES"],
        ["Best HR Environment", ""],
        ["Better Side For Power", ""],
        ["Pitcher Advantage", ""],
        ["Lineup Watch", ""],
    ])

    #
    # HITTER MATCHUPS
    #
    ws = sheet.worksheet("Hitter Matchups")
    ws.clear()
    ws.update([HITTER_HEADERS])

    #
    # PITCHER SLATE
    #
    ws = sheet.worksheet("Pitcher Slate")
    ws.clear()
    ws.update([PITCHER_HEADERS])

    #
    # WEATHER
    #
    ws = sheet.worksheet("Weather")
    ws.clear()
    ws.update([WEATHER_HEADERS])

    #
    # RANKINGS
    #
    ws = sheet.worksheet("Rankings")
    ws.clear()
    ws.update([RANKINGS_HEADERS])

    #
    # MODEL BREAKDOWN
    #
    ws = sheet.worksheet("Model Breakdown")
    ws.clear()
    ws.update([MODEL_BREAKDOWN_HEADERS])

    #
    # MODEL HISTORY
    #
    ws = sheet.worksheet("Model History")
    ws.clear()
    ws.update([HISTORY_HEADERS])

    #
    # CONFIG
    #
    ws = sheet.worksheet("Config")
    ws.clear()
    ws.update(CONFIG_ROWS)

    print("✅ Alpha Wagerz workbook setup complete.")


if __name__ == "__main__":
    setup_workbook()