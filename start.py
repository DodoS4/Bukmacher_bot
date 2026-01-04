import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_TYPES = os.getenv("T_CHAT")           
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") 

# Pobieranie 5 kluczy API
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

STAKE_SINGLE = 40.0  # Bezpieczniejsza stawka przy dużej ilości typów
TAX_RATE = 0.88      # Uwzględnienie polskiego podatku 12%
COUPONS_FILE = "coupons.json"

# Zaktualizowana lista lig (NBA zamiast LM)
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
    try: requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

# ================= STATYSTYKI =================

def send_summary(days=1):
    coupons = load_data(COUPONS_FILE)
    now = datetime.now(timezone.utc)
    start_period = now - timedelta(days=days)
    
    total_staked = 0
    total_won = 0
    wins = 0
    losses = 0
    
    for c in coupons:
        c_time = datetime.fromisoformat(c.get("end_time", "").replace("Z", "+00:00"))
        if c_time > start_period and c.get("status") != "pending":
            total_staked += c["stake"]
            if c["status"] == "win":
                total_won += c["win_val"]
                wins += 1
            else:
                losses += 1
    
    if total_staked > 0:
        profit = round(total_won - total_staked, 2)
        total_bets = wins + losses
        accuracy = round((wins / total_bets) * 100, 1)
        yield_val = round((profit / total_staked) * 100, 2)
        
        title = "📊 PODSUMOWANIE DNIA" if days == 1 else "🔥 RAPORT TYGODNIOWY"
        icon = "📈" if profit >= 0 else "📉"
        
        msg = (
            f"*{title}*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📅 Okres: `Ostatnie {days} dni`\n"
            f"💰 Postawiono: `{total_staked:.2f} PLN`\n"
            f"💵 Wygrano: `{total_won:.2f} PLN`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🎯 Skuteczność: `{accuracy}%`\n"
            f"💎 *Yield: {yield_val:+.2f}%*\n"
            f"{icon} Zysk/Strata: *{profit:+.2f} PLN*\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✅ Trafione: `{wins}` | ❌ Przegrane: `{losses}`"
        )
        send_msg(msg, target="results")

# ================= SELEKCJA Z LOGIKĄ VALUE =================

def find_new_bets():
    coupons = load_data(COUPONS_FILE)
    sent_ids = [m["id"] for c in coupons for m in c["matches"]]
    now = datetime.now(timezone.utc)
    max_future = now + timedelta(hours=48)
    
    potential_bets = []

    for sport_key, league_label in SPORTS.items():
        success = False
        # Rotacja 5 kluczy API
        for key in API_KEYS:
            if success: break
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/", 
                               params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                
                if r.status_code == 429: continue # Klucz wyczerpany, bierzemy następny
                if r.status_code != 200: continue
                
                events = r.json()
                success = True # Pomyślnie pobrano dane dla tej ligi

                for ev in events:
                    if ev["id"] in sent_ids: continue
                    
                    # Znajdź kurs odniesienia na Betfair Exchange
                    betfair_odds = {}
                    for b in ev.get("bookmakers", []):
                        if b['key'] == 'betfair_ex':
                            for outcome in b['markets'][0]['outcomes']:
                                betfair_odds[outcome['name']] = outcome['price']

                    # Szukanie Value u polskich bukmacherów
                    for bookie in ev.get("bookmakers", []):
                        if bookie['key'] in ['pinnacle', 'betfair_ex', 'matchbook']: continue
                        
                        for outcome in bookie['markets'][0]['outcomes']:
                            local_price = outcome['price']
                            o_name = outcome['name']
                            fair_price = betfair_odds.get(o_name)
                            
                            # Filtrujemy kursy (2.10 - 2.80) i sprawdzamy Value
                            if fair_price and 2.10 <= local_price <= 2.80:
                                # Czy po podatku wciąż zarabiamy więcej niż na giełdzie (+3% marginesu)
                                if (local_price * TAX_RATE) > (fair_price * 1.03):
                                    val_pct = round(((local_price * TAX_RATE) / fair_price - 1) * 100, 2)
                                    
                                    potential_bets.append({
                                        "ev": ev, "outcome": outcome, "price": local_price, 
                                        "value": val_pct, "league": league_label, "sport_key": sport_key, 
                                        "commence_time": datetime.fromisoformat(ev['commence_time'].replace('Z', '+00:00'))
                                    })
            except: continue

    # Sortowanie po największym Value i wysyłka wszystkich okazji
    potential_bets = sorted(potential_bets, key=lambda x: x['value'], reverse=True)
    
    for bet in potential_bets:
        win_val = round(STAKE_SINGLE * bet['price'] * TAX_RATE, 2)
        msg = (f"💎 *VALUE DETECTED (+{bet['value']}% )*\n"
               f"━━━━━━━━━━━━━━━\n"
               f"🏟️ `{bet['ev']['home_team']} vs {bet['ev']['away_team']}`\n"
               f"✅ Typ: *{bet['outcome']['name']}*\n"
               f"🏆 {bet['league']}\n"
               f"📅 {bet['commence_time'].strftime('%d.%m %H:%M')} | 📈 Kurs: {bet['price']:.2f}\n"
               f"━━━━━━━━━━━━━━━\n"
               f"💰 Stawka: `{STAKE_SINGLE} PLN` | Wygrana: `{win_val} PLN`")
        
        send_msg(msg, target="types")
        coupons.append({"id": bet['ev']["id"], "status": "pending", "stake": STAKE_SINGLE, "win_val": win_val, "end_time": bet['ev']["commence_time"], "matches": [{"id": bet['ev']["id"], "sport_key": bet['sport_key'], "picked": bet['outcome']['name']}]})
    
    save_data(COUPONS_FILE, coupons)

def check_results():
    coupons = load_data(COUPONS_FILE)
    updated = False
    now = datetime.now(timezone.utc)
    for c in coupons:
        if c.get("status") != "pending": continue
        # Rozliczamy 4h po rozpoczęciu
        if now < datetime.fromisoformat(c["end_time"].replace("Z", "+00:00")) + timedelta(hours=4): continue
        for m in c["matches"]:
            for key in API_KEYS:
                try:
                    r = requests.get(f"https://api.the-odds-api.com/v4/sports/{m['sport_key']}/scores/", params={"apiKey": key, "daysFrom": 3}, timeout=15)
                    score_data = next((s for s in r.json() if s["id"] == m["id"] and s.get("completed")), None)
                    if score_data:
                        h_t, a_t = score_data['home_team'], score_data['away_team']
                        sl = score_data.get("scores", [])
                        h_s = int(next(x['score'] for x in sl if x['name'] == h_t))
                        a_s = int(next(x['score'] for x in sl if x['name'] == a_t))
                        winner = h_t if h_s > a_s else (a_t if a_s > h_s else "Remis")
                        c["status"] = "win" if winner == m['picked'] else "loss"
                        updated = True
                        profit = round(c['win_val'] - c['stake'], 2) if c["status"] == "win" else -c['stake']
                        res_msg = (f"{'✅' if c['status'] == 'win' else '❌'} *WYNIK MECZU*\n━━━━━━━━━━━━━━━\n🏟️ `{h_t} {h_s}:{a_s} {a_t}`\n🎯 Typ: `{m['picked']}`\n💰 Bilans: `{profit:+.2f} PLN`")
                        send_msg(res_msg, target="results")
                    break
                except: continue
    if updated: save_data(COUPONS_FILE, coupons)

def run():
    check_results()
    find_new_bets()
    now = datetime.now(timezone.utc)
    if now.hour >= 20:
        send_summary(days=1)
        if now.weekday() == 6: send_summary(days=7)

if __name__ == "__main__":
    run()
