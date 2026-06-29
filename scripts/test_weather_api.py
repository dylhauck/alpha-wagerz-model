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
data = response.json()

print(f"Status: {response.status_code}")

if response.status_code == 200:
    print(f"Temperature : {data['main']['temp']}°F")
    print(f"Humidity    : {data['main']['humidity']}%")
    print(f"Wind Speed  : {data['wind']['speed']} mph")
    print(f"Wind Dir    : {data['wind']['deg']}°")
    print(f"Conditions  : {data['weather'][0]['description']}")
else:
    print(data)