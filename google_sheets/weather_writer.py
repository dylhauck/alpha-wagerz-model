import json
from pathlib import Path
import gspread
from google.oauth2.service_account import Credentials

SHEET_NAME = "Alpha Wagerz Model"
CREDENTIALS_FILE = "config/google_credentials.json"
WEATHER_FILE = Path("data/processed/weather.json")

HEADERS = [
    "Venue",
    "Temperature",
    "Humidity",
    "Conditions",
    "Wind Direction",
    "Wind Speed",
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


def update_weather_sheet():
    weather = load_json(WEATHER_FILE)

    rows = [
        ["Alpha Wagerz Weather"],
        [],
        HEADERS,
    ]

    for item in weather:
        rows.append([
            item.get("venue", ""),
            item.get("temperature", ""),
            item.get("humidity", ""),
            item.get("conditions", ""),
            item.get("wind_direction", ""),
            item.get("wind_speed", ""),
        ])

    client = get_client()
    sheet = client.open(SHEET_NAME)
    ws = sheet.worksheet("Weather")

    ws.clear()
    ws.update(rows)

    ws.format("A:F", {
        "textFormat": {"foregroundColor": {"red": 0, "green": 0, "blue": 0}},
        "horizontalAlignment": "CENTER",
        "verticalAlignment": "MIDDLE",
    })

    ws.format("A1:F1", {
        "backgroundColor": {"red": 0.02, "green": 0.05, "blue": 0.10},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
            "fontSize": 14,
        },
    })

    ws.format("A3:F3", {
        "backgroundColor": {"red": 0.08, "green": 0.36, "blue": 0.48},
        "textFormat": {
            "foregroundColor": {"red": 1, "green": 1, "blue": 1},
            "bold": True,
        },
    })

    print("✅ Updated Weather sheet")


if __name__ == "__main__":
    update_weather_sheet()