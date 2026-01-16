import requests
import os

key = os.getenv("ODDS_KEY")

url = "https://api.the-odds-api.com/v4/sports/soccer_epl/odds"
params = {
    "apiKey": key,
    "regions": "eu",
    "markets": "h2h",
    "oddsFormat": "decimal"
}

r = requests.get(url, params=params)
print(r.status_code)
print(r.text[:500])