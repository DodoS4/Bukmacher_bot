import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_TYPES = os.getenv("T_CHAT")           
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") 

KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

STAKE_SINGLE = 40.0  
TAX_RATE = 0.88      
VALUE_THRESHOLD = 1.02 # 2% przewagi
COUPONS_FILE = "coupons.json"

SPORTS = {
    "soccer_epl": "⚽ EPL", 
    "soccer_spain_la_liga": "⚽ LA LIGA",
    "soccer_germany_bundesliga": "⚽ BUNDESLIGA", 
    "soccer_italy_serie_a": "⚽ SERIE A",
    "soccer_france_ligue_one": "⚽ LIGUE 1",
    "basketball_nba": "🏀 NBA",
    "soccer_netherlands_eredivisie": "⚽ EREDIVISIE",
    "soccer_portugal_primeira_liga": "⚽ LIGA PORTUGAL"
}

# ================= DIAGNOSTYKA =================
stats = {
    "leagues_checked": 0,
    "matches_found": 0,
    "keys_working": 0,
    "errors": []
}

def send_msg(text, target="types"):
    if not T_TOKEN: return
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT_TYPES
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e: print(f"Błąd wysyłki TG: {e}")

# ================= LOGIKA TESTOWA =================

def find_new_bets():
    coupons = []
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r") as f: coupons = json.load(f)
        except: pass
        
    sent_ids = [m["id"] for c in coupons for m in c.get("matches", [])]
    found_any_value = False

    for sport_key, league_label in SPORTS.items():
        stats["leagues_checked"] += 1
        success = False
        
        for key in API_KEYS:
            if success: break
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/", 
                               params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                
                if r.status_code == 200:
                    stats["keys_working"] = max(stats["keys_working"], API_KEYS.index(key) + 1)
                    events = r.json()
                    stats["matches_found"] += len(events)
                    success = True 

                    for ev in events:
                        if ev["id"] in sent_ids: continue
                        
                        fair_odds = {}
                        for b in ev.get("bookmakers", []):
                            if b['key'] in ['pinnacle', 'betfair_ex']:
                                for outcome in b['markets'][0]['outcomes']:
                                    fair_odds[outcome['name']] = outcome['price']

                        if not fair_odds: continue

                        for bookie in ev.get("bookmakers", []):
                            if bookie['key'] in ['pinnacle', 'betfair_ex']: continue
                            
                            for outcome in bookie['markets'][0]['outcomes']:
                                local_price = outcome['price']
                                reference_price = fair_odds.get(outcome['name'])
                                
                                if reference_price and 2.10 <= local_price <= 2.80:
                                    if (local_price * TAX_RATE) > (reference_price * VALUE_THRESHOLD):
                                        val_pct = round(((local_price * TAX_RATE) / reference_price - 1) * 100, 2)
                                        found_any_value = True
                                        
                                        msg = (f"💎 *VALUE DETECTED (+{val_pct}% )*\n"
                                               f"🏟️ `{ev['home_team']} vs {ev['away_team']}`\n"
                                               f"✅ Typ: *{outcome['name']}* | Kurs: {local_price:.2f}")
                                        send_msg(msg)
                                        
                                        coupons.append({
                                            "id": ev["id"], "status": "pending", "stake": STAKE_SINGLE, 
                                            "win_val": round(STAKE_SINGLE * local_price * TAX_RATE, 2),
                                            "end_time": ev['commence_time'],
                                            "matches": [{"id": ev["id"], "sport_key": sport_key, "picked": outcome['name']}]
                                        })
                elif r.status_code == 401:
                    stats["errors"].append(f"Klucz {key[:5]}... nieprawidłowy")
            except Exception as e:
                stats["errors"].append(str(e))

    with open(COUPONS_FILE, "w") as f: json.dump(coupons[-500:], f, indent=4)
    return found_any_value

def run():
    # Raport startowy - abyś wiedział, że bot ruszył
    start_msg = (f"🚀 *TEST STARTU BOTA*\n"
                 f"🔑 Liczba kluczy w .env: `{len(API_KEYS)}`\n"
                 f"📡 Sprawdzam: `{len(SPORTS)}` lig...")
    send_msg(start_msg)

    found = find_new_bets()

    # Raport końcowy - diagnostyka
    status_icon = "✅" if stats["matches_found"] > 0 else "⚠️"
    diag_msg = (f"{status_icon} *DIAGNOSTYKA KOŃCOWA*\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🏟️ Znaleziono meczów: `{stats['matches_found']}`\n"
                f"🏆 Przeszukano lig: `{stats['leagues_checked']}`\n"
                f"🔑 Działające klucze: `{stats['keys_working']}/{len(API_KEYS)}`\n"
                f"💰 Znaleziono Value: `{'TAK' if found else 'NIE'}`")
    
    if stats["errors"]:
        diag_msg += f"\n❌ *Błędy:* `{stats['errors'][0][:50]}`"
    
    send_msg(diag_msg)

if __name__ == "__main__":
    run()
