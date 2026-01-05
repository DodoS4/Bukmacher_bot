import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_TYPES = os.getenv("T_CHAT")           

KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

STAKE_SINGLE = 40.0  
TAX_RATE = 0.88      # POWRÓT PODATKU
VALUE_MIN = 1.01     # Szukamy min. 1% czystego zysku PO PODATKU
COUPONS_FILE = "coupons.json"

SPORTS = {
    "soccer_epl": "⚽ EPL", 
    "soccer_spain_la_liga": "⚽ LA LIGA",
    "basketball_nba": "🏀 NBA",
    "soccer_italy_serie_a": "⚽ SERIE A",
    "soccer_germany_bundesliga": "⚽ BUNDESLIGA"
}

def load_data(file):
    if not os.path.exists(file): return []
    try:
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def send_msg(text):
    if not T_TOKEN or not T_CHAT_TYPES: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": T_CHAT_TYPES, "text": text, "parse_mode": "Markdown"}, timeout=15)

def find_new_bets():
    coupons = load_data(COUPONS_FILE)
    # Zapamiętujemy ID meczów, żeby nie wysyłać spamu na ten sam mecz
    sent_today = [c.get("event_id") for c in coupons]
    
    potential_bets = []

    for sport_key, league_label in SPORTS.items():
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/", 
                               params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                
                events = r.json()
                for ev in events:
                    if ev['id'] in sent_today: continue # Omijamy mecze już wysłane
                    
                    # 1. Obliczamy średnią światową dla każdego wyniku
                    outcomes_data = {} # { 'Burnley': [kursy...] }
                    for bookie in ev.get("bookmakers", []):
                        for m in bookie['markets']:
                            for out in m['outcomes']:
                                if out['name'] not in outcomes_data: outcomes_data[out['name']] = []
                                outcomes_data[out['name']].append(out['price'])

                    # 2. Szukamy najlepszej okazji u polskiego buka w tym meczu
                    best_val_for_match = None
                    
                    for bookie in ev.get("bookmakers", []):
                        # Pomijamy giełdę przy szukaniu "pomyłki"
                        if bookie['key'] in ['betfair_ex', 'pinnacle']: continue
                        
                        for m in bookie['markets']:
                            for out in m['outcomes']:
                                local_p = out['price']
                                avg_p = sum(outcomes_data[out['name']]) / len(outcomes_data[out['name']])
                                
                                # Czy po podatku przebijamy średnią?
                                if (local_p * TAX_RATE) > (avg_p * VALUE_MIN):
                                    profit = round(((local_p * TAX_RATE) / avg_p - 1) * 100, 1)
                                    if not best_val_for_match or profit > best_val_for_match['val']:
                                        best_val_for_match = {
                                            "val": profit, "p": local_p, "avg": avg_p, 
                                            "name": out['name'], "ev": ev, "league": league_label
                                        }

                    if best_val_for_match:
                        potential_bets.append(best_val_for_match)
                break # Jeśli klucz zadziałał, przejdź do następnej ligi
            except: continue

    # Wysyłka
    for b in potential_bets:
        msg = (f"💎 *VALUE DETECTED (+{b['val']}% )*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"🏟️ `{b['ev']['home_team']} vs {b['ev']['away_team']}`\n"
               f"✅ Typ: *{b['name']}*\n"
               f"🏆 {b['league']}\n"
               f"📈 Kurs: `{b['p']:.2f}` (Średnia: {b['avg']:.2f})\n"
               f"💰 Wygrana (netto): `{round(STAKE_SINGLE * b['p'] * TAX_RATE, 2)} PLN`")
        send_msg(msg)
        coupons.append({"event_id": b['ev']['id']})

    with open(COUPONS_FILE, "w") as f:
        json.dump(coupons[-200:], f)

if __name__ == "__main__":
    find_new_bets()
