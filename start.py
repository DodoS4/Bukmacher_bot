import os
import requests

API_KEY = os.getenv("ODDS_KEY")  # użyj swojego klucza

league = "soccer_epl"

r = requests.get(
    f"https://api.the-odds-api.com/v4/sports/{league}/odds",
    params={"apiKey": API_KEY, "daysFrom": 7}  # 7 dni wprzód
)
print(r.status_code)
print(r.json())