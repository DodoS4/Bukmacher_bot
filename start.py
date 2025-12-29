import requests
import os
import time
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

# Obsługa puli 5 kluczy API
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 PREMIER LEAGUE",
    "soccer_spain_la_liga": "🇪🇸 LA LIGA",
    "soccer_germany_bundesliga": "🇩🇪 BUNDESLIGA",
    "soccer_italy_serie_a": "🇮🇹 SERIE A",
    "soccer_france_ligue_one": "🇫🇷 LIGUE 1",
    "soccer_poland_ekstraklasa": "🇵🇱 EKSTRAKLASA",
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
}

STATE_FILE = "sent.json"
HISTORY_FILE = "history.json"
BANKROLL = 1000              
EV_THRESHOLD = 3.5           
MIN_ODD = 2.00               
MAX_ODD = 6.00               
TAX_RATE = 0.88              
KELLY_FRACTION = 0.1         

# ================= SYSTEM ROZLICZEŃ =================

def load_data(file):
    if not os.path.exists(file): return {} if "sent" in file else []
    try:
        with open(file, "r") as f: return json.load(f)
    except: return {} if "sent" in file else []

def save_data(file, data):
    with open(file, "w") as f: json.dump(data, f)

def fetch_score(sport_key, event_id):
    """Pobiera wynik zakończonego meczu (zużywa 1 kredyt na ligę)."""
    for key in API_KEYS:
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/", 
                             params={"apiKey": key, "daysFrom": 3}, timeout=10)
            if r.status_code == 200:
                for s in r.json():
                    if s["id"] == event_id and s["completed"]:
                        # Pobieranie wyników dla drużyn
                        h_score = int(next(item["score"] for item in s["scores"] if item["name"] == s["home_team"]))
                        a_score = int(next(item["score"] for item in s["scores"] if item["name"] == s["away_team"]))
                        return h_score, a_score
        except: continue
    return None

def check_results():
    """Analizuje historię i wysyła raporty o trafionych typach."""
    history = load_data(HISTORY_FILE)
    if not history: return
    
    now = datetime.now(timezone.utc)
    updated_history = []
    results_summary = {"won": 0, "lost": 0, "profit": 0.0}
    
    for bet in history:
        m_dt = datetime.fromisoformat(bet["date"])
        # Rozliczamy tylko mecze ze statusem 'pending', które zaczęły się min. 4h temu
        if bet.get("status") == "pending" and now > (m_dt + timedelta(hours=4)):
            result = fetch_score(bet["sport"], bet["id"])
            if result:
                h_s, a_s = result
                is_win = False
                # Logika rozliczenia (kto wygrał)
                if bet["pick"] == bet["home"] and h_s > a_s: is_win = True
                elif bet["pick"] == bet["away"] and a_s > h_s: is_win = True
                
                profit = round((bet["stake"] * bet["odd"] * TAX_RATE) - bet["stake"], 2) if is_win else -bet["stake"]
                icon = "✅" if is_win else "❌"
                
                send_msg(f"{icon} **WYNIK MECZU**\n{bet['home']} {h_s}:{a_s} {bet['away']}\n"
                         f"Typ: {bet['pick']} | Kurs: {bet['odd']}\nZysk/Strata: `{profit} zł`")
                
                bet["status"] = "settled"
                bet["final_score"] = f"{h_s}:{a_s}"
                bet["profit"] = profit
        
        # Zachowaj w pliku tylko mecze z ostatnich 7 dni
        if m_dt > (now - timedelta(days=7)):
            updated_history.append(bet)
            
    save_data(HISTORY_FILE, updated_history)

# ================= POMOCNICZE =================

def fair_odds(avg_h, avg_a):
    p_h, p_a = 1 / avg_h, 1 / avg_a
    total = p_h + p_a
    return 1 / (p_h / total), 1 / (p_a / total)

def calculate_kelly_stake(odd, fair_odd):
    real_odd_netto = odd * TAX_RATE
    if real_odd_netto <= 1.0: return 0
    p = 1 / fair_odd
    b = real_odd_netto - 1
    kelly_percent = (b * p - (1 - p)) / b
    return max(0, round(BANKROLL * kelly_percent * KELLY_FRACTION, 2))

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                      json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except: pass

# ================= GŁÓWNA PĘTLA =================

def run():
    now = datetime.now(timezone.utc)
    
    # KROK 1: Rozliczanie wyników raz na dobę (godzina 6:00 UTC)
    if now.hour == 6:
        print("📊 Poranny raport wyników...")
        check_results()

    # KROK 2: Skanowanie kursów
    state = load_data(STATE_FILE)
    if isinstance(state, list): state = {} # Naprawa błędnego formatu
    history = load_data(HISTORY_FILE)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                                 params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=10)
                if r.status_code == 200:
                    matches = r.json(); break
            except: continue

        if not matches: continue

        for m in matches:
            m_id, home, away = m["id"], m["home_team"], m["away_team"]
            m_dt = datetime.fromisoformat(m["commence_time"].replace('Z', '+00:00'))
            
            if m_dt < now or m_dt > (now + timedelta(hours=48)): continue

            odds_h, odds_a = [], []
            for bm in m.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        try:
                            h_o = next(o["price"] for o in market["outcomes"] if o["name"] == home)
                            a_o = next(o["price"] for o in market["outcomes"] if o["name"] == away)
                            odds_h.append(h_o); odds_a.append(a_o)
                        except: continue

            if len(odds_h) < 4: continue
            avg_h, avg_a = sum(odds_h)/len(odds_h), sum(odds_a)/len(odds_a)
            f_h, f_a = fair_odds(avg_h, avg_a)
            max_h, max_a = max(odds_h), max(odds_a)

            ev_h, ev_a = (max_h * TAX_RATE / f_h - 1) * 100, (max_a * TAX_RATE / f_a - 1) * 100
            pick, odd, fair, ev_n = (home, max_h, f_h, ev_h) if ev_h > ev_a else (away, max_a, f_a, ev_a)

            if ev_n >= EV_THRESHOLD and MIN_ODD <= odd <= MAX_ODD and m_id not in state:
                stake = calculate_kelly_stake(odd, fair)
                if stake >= 2.0:
                    msg = (f"💰 *VALUE (+EV)*\n🏆 {sport_label}\n⚔️ **{home} vs {away}**\n"
                           f"━━━━━━━━━━━━━━━\n✅ TYP: *{pick.upper()}*\n📈 Kurs: `{odd:.2f}`\n"
                           f"📊 EV: `+{ev_n:.1f}%` | 💵 Stawka: *{stake} zł*")
                    send_msg(msg)
                    state[m_id] = now.isoformat()
                    history.append({
                        "id": m_id, "home": home, "away": away, "pick": pick, 
                        "odd": odd, "stake": stake, "date": m_dt.isoformat(), 
                        "status": "pending", "sport": sport_key
                    })

    save_data(STATE_FILE, state)
    save_data(HISTORY_FILE, history)

if __name__ == "__main__":
    run()
