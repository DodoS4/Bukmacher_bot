import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_TYPES = os.getenv("T_CHAT")           # Główny kanał
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") # Grupa Wyniki meczy

KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

COUPONS_FILE = "coupons.json"
STAKE_SINGLE = 80.0
TAX_RATE = 0.88

# Ligi do sprawdzenia
SPORTS = ["soccer_epl", "soccer_spain_la_liga", "soccer_germany_bundesliga", 
          "soccer_italy_serie_a", "soccer_poland_ekstraklasa", "basketball_nba"]

# ================= FUNKCJE =================
def send_msg(text, target="types"):
    if not T_TOKEN: return
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT_TYPES
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def load_data(file):
    if not os.path.exists(file): return []
    try:
        with open(file, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data[-500:], f, indent=4)

# ================= ANALIZA I WYSYŁKA TYPÓW =================
def find_new_bets():
    print("--- ROZPOCZYNAM POSZUKIWANIE TYPÓW ---")
    coupons = load_data(COUPONS_FILE)
    sent_ids = [m["id"] for c in coupons for m in c["matches"]]
    
    found_count = 0
    for sport in SPORTS:
        print(f"Sprawdzam ligę: {sport}...")
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds/", 
                               params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                
                events = r.json()
                for ev in events:
                    if ev["id"] in sent_ids: continue
                    
                    # Logika szukania kursu 1.55 - 2.50
                    for bookie in ev.get("bookmakers", []):
                        if bookie['key'] in ['pinnacle', 'williamhill', 'betfair_ex']: continue
                        
                        market = bookie.get("markets", [{}])[0]
                        for outcome in market.get("outcomes", []):
                            price = outcome['price']
                            
                            if 1.55 <= price <= 2.50:
                                # MAMY TYP!
                                win_val = round(STAKE_SINGLE * price * TAX_RATE, 2)
                                
                                # 1. Wyślij na kanał główny
                                msg = (f"🔥 *NOWY TYP DNIA*\n"
                                       f"━━━━━━━━━━━━━━━\n"
                                       f"🏟️ Mecz: `{ev['home_team']} vs {ev['away_team']}`\n"
                                       f"🎯 Typ: `{outcome['name']}`\n"
                                       f"📈 Kurs: `{price:.2f}`\n"
                                       f"💰 Stawka: `{STAKE_SINGLE} PLN`\n"
                                       f"💵 Możliwa wygrana: `{win_val} PLN`")
                                send_msg(msg, target="types")
                                
                                # 2. Zapisz do bazy do późniejszego rozliczenia
                                new_coupon = {
                                    "id": ev["id"],
                                    "status": "pending",
                                    "stake": STAKE_SINGLE,
                                    "win_val": win_val,
                                    "end_time": ev["commence_time"],
                                    "matches": [{
                                        "id": ev["id"],
                                        "sport_key": sport,
                                        "picked": outcome['name'],
                                        "home": ev['home_team'],
                                        "away": ev['away_team']
                                    }]
                                }
                                coupons.append(new_coupon)
                                sent_ids.append(ev["id"])
                                found_count += 1
                                break
                        if found_count > 0: break
                break # Wyjdź z pętli kluczy API dla tej ligi
            except Exception as e:
                print(f"Błąd API: {e}")
    
    save_data(COUPONS_FILE, coupons)
    print(f"Zakończono. Znaleziono nowych typów: {found_count}")

# ================= ROZLICZANIE WYNIKÓW =================
def check_results():
    print("--- SPRAWDZAM WYNIKI ---")
    coupons = load_data(COUPONS_FILE)
    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        # Rozliczamy 4h po meczu
        if now < datetime.fromisoformat(c["end_time"].replace("Z", "+00:00")) + timedelta(hours=4): continue

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
                        res_msg = (f"{icon} *WYNIK MECZU*\n"
                                   f"━━━━━━━━━━━━━━━\n"
                                   f"🏟️ `{h_t} {h_s}:{a_s} {a_t}`\n"
                                   f"🎯 Twój typ: `{m['picked']}`\n"
                                   f"💰 Bilans: `{(c['win_val']-c['stake'] if c['status']=='win' else -c['stake']):+.2f} PLN`")
                        send_msg(res_msg, target="results")
                    break
                except: continue
    if updated: save_data(COUPONS_FILE, coupons)

# ================= START =================
def run():
    check_results()   # Najpierw sprawdź wyniki (do grupy "Wyniki meczy")
    find_new_bets()   # Potem szukaj nowych (na kanał główny)

if __name__ == "__main__":
    run()
