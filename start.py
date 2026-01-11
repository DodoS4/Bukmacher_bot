import requests, json, os
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from dateutil import parser

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
TAX_PL = 0.88 
MIN_EDGE = -0.10 # USTAWIAMY NA MINUS, ŻEBY WYMUSIĆ OFERTY DO TESTU

API_KEYS = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in API_KEYS if k]

# LISTA TESTOWA (ZMNIEJSZONA DO 3, ŻEBY BYŁO SZYBCIEJ)
LEAGUES = {
    "soccer_epl": "⚽ EPL", 
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL"
}

COUPONS_FILE = "coupons.json"

def send_msg(txt):
    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})

print(f"🔍 SKAN START: {datetime.now().strftime('%H:%M:%S')}")
print(f"🔑 Znaleziono aktywnych kluczy API: {len(API_KEYS)}")

if not API_KEYS:
    print("❌ BŁĄD: Brak kluczy API w Secrets!")

for l_key, l_name in LEAGUES.items():
    print(f"📡 Próbuję pobrać: {l_name}...")
    success = False
    for key in API_KEYS:
        url = f"https://api.the-odds-api.com/v4/sports/{l_key}/odds"
        r = requests.get(url, params={"apiKey": key, "markets": "h2h", "regions": "eu"})
        print(f"   Status API ({l_name}): {r.status_code}")
        
        if r.status_code == 200:
            events = r.json()
            print(f"   ✅ Znaleziono {len(events)} meczów")
            # ... (tutaj reszta logiki wysyłania)
            send_msg(f"TEST POŁĄCZENIA: Widzę {len(events)} meczów w {l_name}")
            success = True
            break
    if not success:
        print(f"   ❌ Nie udało się pobrać {l_name}")
