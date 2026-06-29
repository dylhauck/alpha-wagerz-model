import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENWEATHER_API_KEY")

if not API_KEY:
    raise ValueError("OPENWEATHER_API_KEY not found in .env")

lat = 42.3314      # Detroit
lon = -83.0458

url = (
    "https://api.openweathermap.org/data/2.5/weather"
    f"?lat={lat}&lon={lon}"
    f"&appid={API_KEY}"
    "&units=imperial"
)

response = requests.get(url)

print("Status:", response.status_code)
print(response.json())