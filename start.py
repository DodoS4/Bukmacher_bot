import requests
import os
import time
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

KEYS_POOL = [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2"), os.getenv("ODDS_KEY_3")]
API_KEYS = [k for k in KEYS_POOL if k]

SPORTS_CONFIG = {
    "soccer_epl": "⚽ PREMIER LEAGUE",
    "soccer_spain_la_liga": "⚽ LA LIGA",
    "soccer_germany_bundesliga": "⚽ BUNDESLIGA",
    "soccer_italy_serie_a": "⚽ SERIE A",
    "soccer_poland_ekstraklasa": "⚽ EKSTRAKLASA",
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
}

STATE_FILE = "sent.json"
TAX_RATE = 0.88         
BANKROLL = 1000         
KELLY_FRACTION = 0.2    
EV_THRESHOLD = 3.0      

# ================= FUNKCJE BAZY DANYCH =================

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except: pass

# ================= LOGIKA ROZLICZANIA =================

def check_results_and_report():
    print("Rozpoczynam rozliczanie wyników...")
    state = load_state()
    summary = {"wins": 0, "losses": 0, "profit": 0.0}
    changed = False

    # Pobieramy wyniki dla każdego sportu
    for sport_key in SPORTS_CONFIG.keys():
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/",
                                 params={"apiKey": key, "daysFrom": 3}, timeout=15)
                if r.status_code != 200: continue
                
                results = r.json()
                for res in results:
                    m_id = res["id"]
                    s_key = f"{m_id}_v"
                    
                    # Sprawdzamy czy mamy ten mecz w bazie i czy nie jest jeszcze rozliczony
                    if s_key in state and isinstance(state[s_key], dict) and not state[s_key].get("settled"):
                        if not res.get("completed"): continue
                        
                        scores = res.get("scores")
                        if not scores or len(scores) < 2: continue
                        
                        # Wyznaczanie zwycięzcy
                        s1 = int(scores[0]["score"])
                        s2 = int(scores[1]["score"])
                        home_team = res["home_team"]
                        away_team = res["away_team"]
                        
                        actual_winner = "Draw"
                        if s1 > s2: actual_winner = home_team
                        elif s2 > s1: actual_winner = away_team
                        
                        # Porównanie z naszym typem
                        bet = state[s_key]
                        stake = float(bet["stake"])
                        odd = float(bet["odd"])
                        
                        if bet["pick"] == actual_winner:
                            summary["wins"] += 1
                            summary["profit"] += (stake * odd * TAX_RATE) - stake
                        else:
                            summary["losses"] += 1
                            summary["profit"] -= stake
                        
                        state[s_key]["settled"] = True
                        changed = True
                break # Jeśli klucz zadziałał, przejdź do następnego sportu
            except: continue

    if changed:
        save_state(state)
        msg = (f"📊 **DOBOWY RAPORT SKUTECZNOŚCI**\n"
               f"━━━━━━━━━━━━━━━\n"
               f"✅ Trafione: `{summary['wins']}`\n"
               f"❌ Przegrane: `{summary['losses']}`\n"
               f"💰 Zysk netto: `{summary['profit']:.2f} zł`\n"
               f"━━━━━━━━━━━━━━━")
        send_msg(msg)

# ================= SKANOWANIE I POWIADOMIENIA =================

def calculate_kelly_stake(odd, fair_odd):
    real_odd_netto = odd * TAX_RATE
    if real_odd_netto <= 1.0: return 0
    p = 1 / fair_odd
    b = real_odd_netto - 1
    kelly_pc = (b * p - (1 - p)) / b
    return max(0, round(BANKROLL * kelly_pc * KELLY_FRACTION, 2))

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def run_scanner():
    state = load_state()
    now = datetime.now(timezone.utc)
    matches = None

    for key in API_KEYS:
        try:
            r = requests.get("https://api.the-odds-api.com/v4/sports/upcoming/odds/",
                             params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
            if r.status_code == 200:
                matches = r.json()
                break
        except: continue
    
    if not matches: return

    for match in matches:
        sport_key = match["sport_key"]
        if sport_key not in SPORTS_CONFIG: continue
        
        try:
            m_id, home, away = match["id"], match["home_team"], match["away_team"]
            m_dt = datetime.fromisoformat(match["commence_time"].replace('Z', '+00:00'))
            
            if m_dt < now or m_dt > (now + timedelta(hours=48)): continue

            odds_h, odds_a = [], []
            for bm in match.get("bookmakers", []):
                for mkt in bm.get("markets", []):
                    if mkt["key"] == "h2h":
                        h_p = next(float(o["price"]) for o in mkt["outcomes"] if o["name"] == home)
                        a_p = next(float(o["price"]) for o in mkt["outcomes"] if o["name"] == away)
                        odds_h.append(h_p); odds_a.append(a_p)

            if len(odds_h) < 3: continue
            
            avg_h, avg_a = sum(odds_h)/len(odds_h), sum(odds_a)/len(odds_a)
            # Fair odds (uproszczone bez marży)
            total_p = (1/avg_h) + (1/avg_a)
            f_h, f_a = 1/((1/avg_h)/total_p), 1/((1/avg_a)/total_p)
            
            max_h, max_a = max(odds_h), max(odds_a)
            ev_h = (max_h * TAX_RATE / f_h - 1) * 100
            ev_a = (max_a * TAX_RATE / f_a - 1) * 100

            if ev_h > ev_a: pick, odd, fair, ev_n = home, max_h, f_h, ev_h
            else: pick, odd, fair, ev_n = away, max_a, f_a, ev_a

            if ev_n >= EV_THRESHOLD and f"{m_id}_v" not in state:
                stake = calculate_kelly_stake(odd, fair)
                if stake > 0:
                    msg = (f"💎 **VALUE (+EV)**\n🏆 {SPORTS_CONFIG[sport_key]}\n"
                           f"⚔️ **{home} vs {away}**\n━━━━━━━━━━━━━━━\n"
                           f"✅ TYP: *{pick}*\n📈 Kurs: `{odd:.2f}`\n🔥 EV: `+{ev_n:.1f}%` | Stawka: `{stake} zł`\n"
                           f"━━━━━━━━━━━━━━━")
                    send_msg(msg)
                    state[f"{m_id}_v"] = {
                        "time": now.isoformat(),
                        "pick": pick,
                        "odd": odd,
                        "stake": stake,
                        "settled": False
                    }
                    save_state(state)
        except: continue

if __name__ == "__main__":
    run_scanner()
    # Raportowanie o 23:00 UTC
    if datetime.now(timezone.utc).hour == 23:
        check_results_and_report()
