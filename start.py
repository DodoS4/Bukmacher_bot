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
COUPONS_FILE = "coupons.json"

# Ligi, które w tej chwili (poniedziałek) mają najwięcej zdarzeń
SPORTS = {
    "soccer_epl": "⚽ EPL", 
    "soccer_spain_la_liga": "⚽ LA LIGA",
    "basketball_nba": "🏀 NBA",
    "soccer_italy_serie_a": "⚽ SERIE A",
    "soccer_france_ligue_one": "⚽ LIGUE 1"
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

# ================= SILNIK AGRESYWNEGO VALUE =================

def find_new_bets():
    coupons = load_data(COUPONS_FILE)
    sent_ids = [m["id"] for c in coupons for m in c.get("matches", [])]
    
    found_count = 0

    for sport_key, league_label in SPORTS.items():
        success = False
        for key in API_KEYS:
            if success: break
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/", 
                               params={"apiKey": key, "regions": "eu", "markets": "h2h,totals"}, timeout=15)
                
                if r.status_code != 200:
                    print(f"Klucz {key[:5]}... błąd: {r.status_code}")
                    continue
                
                events = r.json()
                success = True
                
                for ev in events:
                    for market_data in ev.get("bookmakers", []):
                        # Szukamy okazji u polskich buków (np. STS, Fortuna, Betclic - w API jako 'legalne' eu)
                        if market_data['key'] in ['pinnacle', 'betfair_ex']: continue
                        
                        for m_type in market_data['markets']:
                            for outcome in m_type['outcomes']:
                                local_price = outcome['price']
                                
                                # Wyznaczamy cenę rynkową (średnią lub z Pinnacle)
                                ref_prices = []
                                for b in ev.get("bookmakers", []):
                                    if b['key'] in ['pinnacle', 'betfair_ex', 'williamhill']:
                                        for m_ref in b['markets']:
                                            if m_ref['key'] == m_type['key']:
                                                for o_ref in m_ref['outcomes']:
                                                    if o_ref['name'] == outcome['name'] and o_ref.get('point') == outcome.get('point'):
                                                        ref_prices.append(o_ref['price'])
                                
                                if not ref_prices: continue
                                avg_ref = sum(ref_prices) / len(ref_prices)
                                
                                # AGRESYWNY FILTR: Jeśli kurs u nas jest wyższy niż średnia światowa o 5%
                                # (To zrekompensuje brak odliczania podatku w teście)
                                if local_price > (avg_ref * 1.05):
                                    eid = f"{ev['id']}_{outcome['name']}_{outcome.get('point','')}"
                                    if eid in sent_ids: continue
                                    
                                    val = round((local_price / avg_ref - 1) * 100, 1)
                                    target = f"{outcome['name']} {outcome.get('point', '')}".strip()
                                    
                                    msg = (f"🚀 *TURBO VALUE DETECTED*\n"
                                           f"🏟️ `{ev['home_team']} vs {ev['away_team']}`\n"
                                           f"✅ Typ: *{target}*\n"
                                           f"📈 Kurs: `{local_price:.2f}` (Średnia: {avg_ref:.2f})\n"
                                           f"💎 Przewaga: `+{val}%`")
                                    send_msg(msg)
                                    
                                    coupons.append({"matches": [{"id": eid}]})
                                    found_count += 1
                                    if found_count >= 3: break # Nie spamuj
            except: continue

    with open(COUPONS_FILE, "w") as f:
        json.dump(coupons[-100:], f)

if __name__ == "__main__":
    find_new_bets()
