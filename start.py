import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_TYPES = os.getenv("T_CHAT")           # Główny kanał na typy
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") # Grupa na wyniki: -5257529572

KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

STAKE_SINGLE = 80.0
TAX_RATE = 0.88
COUPONS_FILE = "coupons.json"

# Konfiguracja lig
SPORTS = {
    "soccer_epl": "⚽ EPL", 
    "soccer_spain_la_liga": "⚽ LA LIGA",
    "soccer_germany_bundesliga": "⚽ BUNDESLIGA", 
    "soccer_italy_serie_a": "⚽ SERIE A",
    "soccer_poland_ekstraklasa": "⚽ EKSTRAKLASA",
    "basketball_nba": "🏀 NBA"
}

# ================= FUNKCJE POMOCNICZE =================

def load_data(file):
    if not os.path.exists(file): return []
    try:
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data[-500:], f, indent=4)

def send_msg(text, target="types"):
    if not T_TOKEN: return
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT_TYPES
    if not chat_id: return
    
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: 
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

# ================= SZUKANIE TYPÓW (WYGLĄD ZE ZDJĘCIA) =================

def find_new_bets():
    coupons = load_data(COUPONS_FILE)
    sent_ids = [m["id"] for c in coupons for m in c["matches"]]
    
    for sport_key, league_label in SPORTS.items():
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/", 
                               params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                events = r.json()
                
                for ev in events:
                    if ev["id"] in sent_ids: continue
                    
                    for bookie in ev.get("bookmakers", []):
                        # Pomijamy giełdy i zagraniczne bez podatku dla realizmu kursu
                        if bookie['key'] in ['pinnacle', 'betfair_ex']: continue
                        
                        market = bookie.get("markets", [{}])[0]
                        for outcome in market.get("outcomes", []):
                            price = outcome['price']
                            
                            # Twoje widełki kursowe
                            if 1.55 <= price <= 2.50:
                                win_val = round(STAKE_SINGLE * price * TAX_RATE, 2)
                                commence_time = datetime.fromisoformat(ev['commence_time'].replace('Z', '+00:00'))
                                date_str = commence_time.strftime("%d.%m %H:%M")

                                # FORMATOWANIE WIADOMOŚCI IDENTYCZNE ZE ZDJĘCIEM
                                msg = (
                                    f"🎯 *SINGLE*\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"🏟️ `{ev['home_team']} vs {ev['away_team']}`\n"
                                    f"✅ Typ: *{outcome['name']}*\n"
                                    f"🏆 {league_label}\n"
                                    f"📅 {date_str} | 📈 {price:.2f}\n"
                                    f"━━━━━━━━━━━━━━━\n"
                                    f"💰 Stawka: `{STAKE_SINGLE} PLN` | Wygrana: `{win_val} PLN`"
                                )
                                
                                send_msg(msg, target="types")
                                
                                # Zapis do bazy do rozliczenia
                                coupons.append({
                                    "id": ev["id"],
                                    "status": "pending",
                                    "stake": STAKE_SINGLE,
                                    "win_val": win_val,
                                    "end_time": ev["commence_time"],
                                    "matches": [{"id": ev["id"], "sport_key": sport_key, "picked": outcome['name']}]
                                })
                                sent_ids.append(ev["id"])
                                break
                        if ev["id"] in sent_ids: break
                break
            except: continue
    save_data(COUPONS_FILE, coupons)

# ================= ROZLICZANIE WYNIKÓW =================

def check_results():
    coupons = load_data(COUPONS_FILE)
    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        end_time = datetime.fromisoformat(c["end_time"].replace("Z", "+00:00"))
        if now < end_time + timedelta(hours=4): continue

        for m in c["matches"]:
            for key in API_KEYS:
                try:
                    r = requests.get(f"https://api.the-odds-api.com/v4/sports/{m['sport_key']}/scores/", 
                                   params={"apiKey": key, "daysFrom": 3}, timeout=15)
                    if r.status_code != 200: continue
                    
                    score_data = next((s for s in r.json() if s["id"] == m["id"] and s.get("completed")), None)
                    if score_data:
                        h_t, a_t = score_data['home_team'], score_data['away_team']
                        sl = score_data.get("scores", [])
                        h_s = int(next(x['score'] for x in sl if x['name'] == h_t))
                        a_s = int(next(x['score'] for x in sl if x['name'] == a_t))
                        
                        winner = h_t if h_s > a_s else (a_t if a_s > h_s else "Remis")
                        c["status"] = "win" if winner == m['picked'] else "loss"
                        updated = True
                        
                        icon = "✅" if c["status"] == "win" else "❌"
                        profit = round(c['win_val'] - c['stake'], 2) if c["status"] == "win" else -c['stake']
                        
                        # Wynik do grupy WYNIKI MECZY
                        res_msg = (f"{icon} *ROZLICZENIE*\n"
                                   f"🏟️ `{h_t} {h_s}:{a_s} {a_t}`\n"
                                   f"🎯 Typ: `{m['picked']}`\n"
                                   f"💰 Bilans: `{profit:+.2f} PLN`")
                        send_msg(res_msg, target="results")
                    break
                except: continue
    if updated: save_data(COUPONS_FILE, coupons)

# ================= URUCHOMIENIE =================

def run():
    check_results()
    find_new_bets()

if __name__ == "__main__":
    run()
