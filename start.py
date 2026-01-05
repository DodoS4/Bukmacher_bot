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
VALUE_MIN = 1.01     
COUPONS_FILE = "coupons.json"

SPORTS = {
    "soccer_epl": "⚽ EPL", 
    "soccer_spain_la_liga": "⚽ LA LIGA",
    "basketball_nba": "🏀 NBA",
    "soccer_italy_serie_a": "⚽ SERIE A",
    "soccer_germany_bundesliga": "⚽ BUNDESLIGA"
}

# ================= POMOCNICZE =================

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
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

# ================= ROZLICZANIE I STATYSTYKI =================

def check_results():
    coupons = load_data(COUPONS_FILE)
    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        try:
            start_time = datetime.fromisoformat(c["end_time"].replace("Z", "+00:00"))
            if now < start_time + timedelta(hours=4): continue
            
            for key in API_KEYS:
                try:
                    r = requests.get(f"https://api.the-odds-api.com/v4/sports/{c['sport_key']}/scores/", 
                                   params={"apiKey": key, "daysFrom": 3}, timeout=15)
                    score_data = next((s for s in r.json() if s["id"] == c["event_id"] and s.get("completed")), None)
                    
                    if score_data:
                        h_t, a_t = score_data['home_team'], score_data['away_team']
                        sl = score_data.get("scores", [])
                        h_s = int(next(x['score'] for x in sl if x['name'] == h_t))
                        a_s = int(next(x['score'] for x in sl if x['name'] == a_t))
                        
                        winner = h_t if h_s > a_s else (a_t if a_s > h_s else "Draw")
                        c["status"] = "win" if winner == c['picked'] else "loss"
                        updated = True
                        
                        profit = round(c['win_val'] - c['stake'], 2) if c["status"] == "win" else -c['stake']
                        res_msg = (f"{'✅' if c['status'] == 'win' else '❌'} *WYNIK MECZU*\n"
                                   f"━━━━━━━━━━━━━━━\n"
                                   f"🏟️ `{h_t} {h_s}:{a_s} {a_t}`\n"
                                   f"🎯 Typ: `{c['picked']}` | Bilans: `{profit:+.2f} PLN`")
                        send_msg(res_msg, target="results")
                    break
                except: continue
        except: continue
    if updated: save_data(COUPONS_FILE, coupons)

def send_summary(days=1):
    coupons = load_data(COUPONS_FILE)
    now = datetime.now(timezone.utc)
    start_period = now - timedelta(days=days)
    t_stake, t_won, wins, losses = 0, 0, 0, 0
    
    for c in coupons:
        try:
            c_time = datetime.fromisoformat(c.get("end_time", "").replace("Z", "+00:00"))
            if c_time > start_period and c.get("status") != "pending":
                t_stake += c["stake"]
                if c["status"] == "win":
                    t_won += c["win_val"]
                    wins += 1
                else: losses += 1
        except: continue
    
    if t_stake > 0:
        profit = round(t_won - t_stake, 2)
        yield_val = round((profit / t_stake) * 100, 2)
        title = "📊 PODSUMOWANIE DNIA" if days == 1 else "🔥 RAPORT TYGODNIOWY"
        msg = (f"*{title}*\n━━━━━━━━━━━━━━━\n"
               f"💰 Postawiono: `{t_stake:.2f} PLN` | Zysk: *{profit:+.2f} PLN*\n"
               f"💎 Yield: `{yield_val:+.2f}%` | Skuteczność: `{round(wins/(wins+losses)*100,1)}%`\n"
               f"✅ `{wins}` | ❌ `{losses}`")
        send_msg(msg, target="results")

# ================= WYSZUKIWANIE TYPÓW =================

def find_new_bets():
    coupons = load_data(COUPONS_FILE)
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
                    if ev['id'] in sent_today: continue
                    outcomes_prices = {}
                    for b in ev.get("bookmakers", []):
                        for m in b['markets']:
                            for out in m['outcomes']:
                                if out['name'] not in outcomes_prices: outcomes_prices[out['name']] = []
                                outcomes_prices[out['name']].append(out['price'])
                    
                    best_option = None
                    for bookie in ev.get("bookmakers", []):
                        if bookie['key'] in ['betfair_ex', 'pinnacle']: continue
                        for m in bookie['markets']:
                            for out in m['outcomes']:
                                local_p, avg_p = out['price'], sum(outcomes_prices[out['name']])/len(outcomes_prices[out['name']])
                                if (local_p * TAX_RATE) > (avg_p * VALUE_MIN):
                                    profit = round(((local_p * TAX_RATE) / avg_p - 1) * 100, 1)
                                    if not best_option or profit > best_option['val']:
                                        best_option = {"val": profit, "p": local_p, "avg": avg_p, "name": out['name'], "ev": ev, "sport": sport_key}
                    if best_option: potential_bets.append(best_option)
                break 
            except: continue

    for b in potential_bets:
        dt = datetime.fromisoformat(b['ev']['commence_time'].replace('Z', '+00:00'))
        win_netto = round(STAKE_SINGLE * b['p'] * TAX_RATE, 2)
        msg = (f"💎 *VALUE DETECTED (+{b['val']}% )*\n━━━━━━━━━━━━━━━\n"
               f"🏟️ `{b['ev']['home_team']} vs {b['ev']['away_team']}`\n"
               f"📅 Start: `{dt.strftime('%d.%m %H:%M')}`\n"
               f"✅ Typ: *{b['name']}* | 🏆 {SPORTS[b['sport']]}\n━━━━━━━━━━━━━━━\n"
               f"📈 Kurs: `{b['p']:.2f}` | 💰 Wygrana: `{win_netto} PLN`")
        send_msg(msg)
        coupons.append({"event_id": b['ev']['id'], "status": "pending", "stake": STAKE_SINGLE, "win_val": win_netto, "end_time": b['ev']['commence_time'], "picked": b['name'], "sport_key": b['sport']})
    save_data(COUPONS_FILE, coupons)

def run():
    check_results()
    find_new_bets()
    now = datetime.now(timezone.utc)
    if now.hour == 20:
        send_summary(days=1)
        if now.weekday() == 6: send_summary(days=7)

if __name__ == "__main__":
    run()
