import requests
import os
import time
import json
from datetime import datetime, timedelta, timezone

# ======================== KONFIGURACJA ========================
# Wpisz swoje dane między cudzysłowy:
T_TOKEN = "TWÓJ_TOKEN_TELEGRAM"
T_CHAT = "TWÓJ_ID_CZATU"

# Możesz wpisać od 1 do 3 kluczy
API_KEYS = [
    "KLUCZ_API_1",
    "KLUCZ_API_2",
    "KLUCZ_API_3"
]

# Konfiguracja lig (Bot będzie filtrował tylko te z listy upcoming)
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
EV_THRESHOLD = 3.0      
PEWNIAK_EV_THRESHOLD = 7.0
PEWNIAK_MAX_ODD = 2.60
MIN_ODD = 1.55          
MAX_HOURS_AHEAD = 48    

BANKROLL = 1000         
KELLY_FRACTION = 0.2    
TAX_RATE = 0.88         

# ======================== LOGIKA POMOCNICZA ========================

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, "r") as f: 
            data = json.load(f)
            # Jeśli plik jest w starym formacie (nie jest słownikiem słowników), zresetuj go
            first_val = next(iter(data.values())) if data else None
            if first_val and not isinstance(first_val, dict):
                return {}
            return data
    except: return {}

def save_state(state):
    with open(STATE_FILE, "w") as f: json.dump(state, f)

def calculate_kelly_stake(odd, fair_odd):
    real_odd_netto = odd * TAX_RATE
    if real_odd_netto <= 1.0: return 0
    p = 1 / fair_odd
    b = real_odd_netto - 1
    kelly_pc = (b * p - (1 - p)) / b
    return max(0, round(BANKROLL * kelly_pc * KELLY_FRACTION, 2))

def fair_odds(avg_h, avg_a):
    p_h, p_a = 1 / avg_h, 1 / avg_a
    total = p_h + p_a
    return 1 / (p_h / total), 1 / (p_a / total)

def send_msg(text):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except: print("Błąd wysyłania do Telegrama")

# ======================== MODUŁY GŁÓWNE ========================

def check_results_and_report():
    print("Sprawdzam wyniki...")
    state = load_state()
    summary = {"wins": 0, "losses": 0, "profit": 0.0}
    changed = False

    for sport_key in SPORTS_CONFIG.keys():
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/",
                                 params={"apiKey": key, "daysFrom": 1}, timeout=10)
                if r.status_code != 200: continue
                scores = r.json()
                
                for res in scores:
                    m_id = res["id"]
                    s_key = f"{m_id}_v"
                    if s_key in state and isinstance(state[s_key], dict) and not state[s_key].get("settled"):
                        if not res.get("completed"): continue
                        s_data = res.get("scores", [])
                        if len(s_data) < 2: continue
                        
                        h_score = int(s_data[0]["score"])
                        a_score = int(s_data[1]["score"])
                        winner = res["home_team"] if h_score > a_score else (res["away_team"] if a_score > h_score else "Draw")

                        bet = state[s_key]
                        if bet["pick"] == winner:
                            summary["wins"] += 1
                            summary["profit"] += (bet["stake"] * bet["odd"] * TAX_RATE) - bet["stake"]
                        else:
                            summary["losses"] += 1
                            summary["profit"] -= bet["stake"]
                        
                        state[s_key]["settled"] = True
                        changed = True
                break 
            except: continue

    if changed:
        save_state(state)
        if (summary["wins"] + summary["losses"]) > 0:
            msg = (f"📊 **DOBOWY RAPORT SKUTECZNOŚCI**\n"
                   f"━━━━━━━━━━━━━━━\n"
                   f"✅ Trafione: `{summary['wins']}`\n"
                   f"❌ Przegrane: `{summary['losses']}`\n"
                   f"💰 Zysk/Strata netto: `{summary['profit']:.2f} zł`\n"
                   f"━━━━━━━━━━━━━━━")
            send_msg(msg)

def run_scanner():
    state = load_state()
    now = datetime.now(timezone.utc)
    matches = None

    for key in API_KEYS:
        try:
            r = requests.get("https://api.the-odds-api.com/v4/sports/upcoming/odds/",
                             params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=10)
            if r.status_code == 200:
                matches = r.json()
                break
        except: continue
    
    if not matches: 
        print("Nie udało się pobrać kursów. Sprawdź klucze API.")
        return

    for match in matches:
        sport_key = match["sport_key"]
        if sport_key not in SPORTS_CONFIG: continue
        
        try:
            m_id, home, away = match["id"], match["home_team"], match["away_team"]
            m_dt = datetime.fromisoformat(match["commence_time"].replace('Z', '+00:00'))
            if m_dt < now or m_dt > (now + timedelta(hours=MAX_HOURS_AHEAD)): continue

            odds_h, odds_a = [], []
            for bm in match.get("bookmakers", []):
                for mkt in bm.get("markets", []):
                    if mkt["key"] == "h2h":
                        try:
                            h_p = next(o["price"] for o in mkt["outcomes"] if o["name"] == home)
                            a_p = next(o["price"] for o in mkt["outcomes"] if o["name"] == away)
                            odds_h.append(h_p); odds_a.append(a_p)
                        except: continue

            if len(odds_h) < 3: continue
            f_h, f_a = fair_odds(sum(odds_h)/len(odds_h), sum(odds_a)/len(odds_a))
            max_h, max_a = max(odds_h), max(odds_a)
            
            ev_h = (max_h * TAX_RATE / f_h - 1) * 100
            ev_a = (max_a * TAX_RATE / f_a - 1) * 100

            if ev_h > ev_a: pick, odd, fair, ev_n = home, max_h, f_h, ev_h
            else: pick, odd, fair, ev_n = away, max_a, f_a, ev_a

            if ev_n >= EV_THRESHOLD and odd >= MIN_ODD and f"{m_id}_v" not in state:
                stake = calculate_kelly_stake(odd, fair)
                if stake > 0:
                    is_pewniak = ev_n >= PEWNIAK_EV_THRESHOLD and odd <= PEWNIAK_MAX_ODD
                    header = "🔥 💎 **PEWNIAK (+EV)** 🔥" if is_pewniak else "💎 *VALUE (+EV)*"
                    msg = (f"{header}\n🏆 {SPORTS_CONFIG[sport_key]}\n⚔️ **{home} vs {away}**\n"
                           f"━━━━━━━━━━━━━━━\n"
                           f"{'⭐' if is_pewniak else '✅'} STAWIAJ NA: *{pick}*\n"
                           f"📈 Kurs: `{odd:.2f}` (Fair: {fair:.2f})\n"
                           f"🔥 EV netto: `+{ev_n:.1f}%`\n"
                           f"💰 Sugerowana stawka: *{stake} zł*\n"
                           f"⏰ {m_dt.strftime('%d.%m %H:%M')} UTC\n"
                           f"━━━━━━━━━━━━━━━")
                    send_msg(msg)
                    state[f"{m_id}_v"] = {"pick": pick, "odd": odd, "stake": stake, "settled": False}
                    save_state(state)
        except: continue

# ======================== PĘTLA GŁÓWNA ========================

if __name__ == "__main__":
    print(f"Bot wystartował o {datetime.now().strftime('%H:%M:%S')}")
    last_report_day = datetime.now().day
    
    while True:
        try:
            run_scanner()
            
            # Sprawdzanie wyników raz na dobę
            if datetime.now().day != last_report_day:
                check_results_and_report()
                last_report_day = datetime.now().day
                
            print(f"Skanowanie OK. Następne za 1h...")
            time.sleep(3600) 
        except Exception as e:
            print(f"Błąd pętli: {e}")
            time.sleep(60)

