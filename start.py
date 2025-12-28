import requests
import os
import time
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

KEYS_POOL = [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
    os.getenv("ODDS_KEY_4"),
]
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
MAX_DAYS = 3            
EV_THRESHOLD = 3.0      
PEWNIAK_EV_THRESHOLD = 7.0
PEWNIAK_MAX_ODD = 2.60
MIN_ODD = 1.55          
MAX_HOURS_AHEAD = 48    

BANKROLL = 1000         
KELLY_FRACTION = 0.2    
TAX_RATE = 0.88         

# ================= POMOCNICZE =================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        print(f"Blad zapisu pliku: {e}")

def clean_state(state):
    now = datetime.now(timezone.utc)
    new_state = {}
    for key, val in state.items():
        try:
            # Obsluga starego formatu (string) i nowego (dict)
            ts = val if isinstance(val, str) else val.get("time", "")
            if not ts: continue
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if now - dt <= timedelta(days=MAX_DAYS):
                new_state[key] = val
        except:
            continue
    return new_state

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

# ================= KOMUNIKACJA =================

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except:
        pass

def format_value_message(sport_label, home, away, pick, odd, fair, ev_netto, m_dt, stake):
    is_pewniak = ev_netto >= PEWNIAK_EV_THRESHOLD and odd <= PEWNIAK_MAX_ODD
    header = "🔥 💎 **PEWNIAK (+EV)** 🔥" if is_pewniak else "💎 *VALUE (+EV)*"
    pick_icon = "⭐" if is_pewniak else "✅"
    
    msg = (
        f"{header}\n"
        f"🏆 {sport_label}\n"
        f"⚔️ **{home} vs {away}**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{pick_icon} STAWIAJ NA: *{pick}*\n"
        f"📈 Kurs: `{odd:.2f}` (Fair: {fair:.2f})\n"
        f"🔥 EV netto: `+{ev_netto:.1f}%`\n"
        f"💰 Sugerowana stawka: *{stake} zł*\n"
        f"⏰ {m_dt.strftime('%d.%m %H:%M')} UTC\n"
        f"━━━━━━━━━━━━━━━"
    )
    return msg

# ================= GLOWNA LOGIKA =================

def run():
    if not API_KEYS:
        print("Brak kluczy API!")
        return
        
    state = clean_state(load_state())
    now = datetime.now(timezone.utc)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                                 params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=10)
                if r.status_code == 200:
                    matches = r.json()
                    break
            except:
                continue
        
        if not matches:
            continue

        for match in matches:
            try:
                m_id = match["id"]
                home, away = match["home_team"], match["away_team"]
                m_dt = datetime.fromisoformat(match["commence_time"].replace('Z', '+00:00'))

                if m_dt < now or m_dt > (now + timedelta(hours=MAX_HOURS_AHEAD)):
                    continue

                odds_h, odds_a = [], []
                for bm in match.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market["key"] == "h2h":
                            h_val = next(o["price"] for o in market["outcomes"] if o["name"] == home)
                            a_val = next(o["price"] for o in market["outcomes"] if o["name"] == away)
                            odds_h.append(h_val)
                            odds_a.append(a_val)

                if len(odds_h) < 3:
                    continue

                avg_h, avg_a = sum(odds_h)/len(odds_h), sum(odds_a)/len(odds_a)
                fair_h, fair_a = fair_odds(avg_h, avg_a)
                max_h, max_a = max(odds_h), max(odds_a)

                ev_h_net = (max_h * TAX_RATE / fair_h - 1) * 100
                ev_a_net = (max_a * TAX_RATE / fair_a - 1) * 100

                if ev_h_net > ev_a_net:
                    pick, odd, fair, ev_n = home, max_h, fair_h, ev_h_net
                else:
                    pick, odd, fair, ev_n = away, max_a, fair_a, ev_a_net

                if ev_n >= EV_THRESHOLD and odd >= MIN_ODD and f"{m_id}_v" not in state:
                    stake = calculate_kelly_stake(odd, fair)
                    if stake > 0:
                        msg = format_value_message(sport_label, home, away, pick, odd, fair, ev_n, m_dt, stake)
                        send_msg(msg)
                        # Zapisujemy jako slownik, by ulatwic rozliczanie w przyszlosci
                        state[f"{m_id}_v"] = {
                            "time": now.isoformat(),
                            "pick": pick,
                            "odd": odd,
                            "stake": stake
                        }
                        save_state(state)
                        time.sleep(1) 
            except:
                continue

if __name__ == "__main__":
    run()
