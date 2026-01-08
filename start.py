import os
import requests
import json

# Pobranie kluczy z GitHub Secrets lub środowiska lokalnego
API_KEYS = [k for k in [
    os.getenv("ODDS_KEY_1"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
    os.getenv("ODDS_KEY_5")
] if k]

def check_ligues_for_key(key):
    try:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports", params={"apiKey": key}, timeout=10)
        if r.status_code != 200:
            print(f"❌ Klucz {key[:5]}*** niedostępny, kod {r.status_code}")
            return []
        sports = r.json()
        active_sports = [s["key"] for s in sports if s.get("active", False)]
        print(f"✅ Klucz {key[:5]}*** ma dostęp do lig: {active_sports}")
        return active_sports
    except Exception as e:
        print(f"⚠ Wyjątek dla klucza {key[:5]}***: {e}")
        return []

all_active_leagues = set()
for key in API_KEYS:
    active = check_ligues_for_key(key)
    all_active_leagues.update(active)

print("\n📄 Wszystkie dostępne ligi dla Twoich kluczy:")
for lg in sorted(all_active_leagues):
    print(f" - {lg}")

# Zapis do pliku JSON, można potem użyć w bot.py
with open("active_leagues.json", "w", encoding="utf-8") as f:
    json.dump(list(all_active_leagues), f, indent=4)