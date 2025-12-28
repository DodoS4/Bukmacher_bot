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
EV_THRESHOLD = 3.0      # % EV netto
PEWNIAK_EV_THRESHOLD = 7.0
PEWNIAK_MAX_ODD = 2.60
MIN_ODD = 1.55
MAX_HOURS_AHEAD = 48

BANKROLL = 1000
KELLY_FRACTION = 0.2
TAX_RATE = 0.88

# ================= POMOCNICZE =================

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    with open(STATE_FILE, "r") as f: return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f: json.dump(state, f)

def clean_state(state):
    now = datetime.now(timezone.utc)
    new_state = {}
    for key, ts in state.items():
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if now - dt <= timedelta(days=MAX_DAYS): new_state[key] = ts
        except: continue
    return new_state

def calculate_kelly_stake(odd, fair_odd):
    real_odd_netto = odd * TAX_RATE
    if real_odd_netto <= 1.0: return 0
    p, b = 1/fair_odd, real_odd_netto - 1
    kelly = (b * p - (1-p)) / b
    return max(0, round(BANKROLL * kelly * KELLY_FRACTION, 2))

def fair_odds(avg_h, avg_a):
    total = (1/avg_h) + (1/avg_a)
    return 1/((1/avg_h)/total), 1/((1/avg_a)/total)

# ================= FORMATOWANIE WIADOMOŚCI =================

def format_value_message(sport_label, home, away, pick, odd, fair, ev_netto, m_dt, stake, bookmaker_name):
    is_pewniak = ev_netto >= PEWNIAK_EV_THRESHOLD and odd <= PEWNIAK_MAX_ODD
    header = "🔥 💎 **PEWNIAK (+EV)** 🔥" if is_pewniak else "💎 *VALUE (+EV)*"
    pick_icon = "⭐" if is_pewniak else "✅"
    
    msg = (
        f"{header}\n"
        f"🏆 {sport_label}\n"
        f"⚔️ **{home} vs {away}**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{pick_icon} STAWIAJ NA: *{pick}*\n"
        f"🏛️ Bukmacher: `{bookmaker_name}`\n"
        f"📈 Kurs: `{odd:.2f}` (Fair: {fair:.2f})\n"
        f"🔥 EV netto: `+{ev_netto:.1f}%`\n"
        f"💰 Sugerowana stawka: *{stake} zł*\n"
        f"⏰ {m_dt.strftime('%d.%m %H:%M')} UTC\n"
        f"━━━━━━━━━━━━━━━"
    )
    return msg

# ================= GŁÓWNA PĘTLA =================

def run():
    if not API_KEYS: return
    state = clean_state(load_state())
    save_state(state)
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
            except: continue
        
        if not matches: continue

        for match in matches:
            try:
                m_id, home, away = match["id"], match["home_team"], match["away_team"]
                m_dt = datetime.fromisoformat(match["commence_time"].replace('Z', '+00:00'))
                if m_dt < now or m_dt > (now + timedelta(hours=MAX_HOURS_AHEAD)): continue

                # Zbieranie kursów i nazw bukmacherów
                odds_data = {"h": [], "a": []}
                for bm in match.get("bookmakers", []):
                    title = bm["title"]
                    for market in bm.get("markets", []):
                        if market["key"] == "h2h":
                            h_val = next(o["price"] for o in market["outcomes"] if o["name"] == home)
                            a_val = next(o["price"] for o in market["outcomes"] if o["name"] == away)
                            odds_data["h"].append({"price": h_val, "bookie": title})
                            odds_data["a"].append({"price": a_val, "bookie": title})

                if len(odds_data["h"]) < 3: continue

                # Obliczenia
                avg_h = sum(o["price"] for o in odds_data["h"]) / len(odds_data["h"])
                avg_a = sum(o["price"] for o in odds_data["a"]) / len(odds_data["a"])
                fair_h, fair_a = fair_odds(avg_h, avg_a)

                best_h = max(odds_data["h"], key=lambda x: x["price"])
                best_a = max(odds_data["a"], key=lambda x: x["price"])

                ev_h_net = (best_h["price"] * TAX_RATE / fair_h - 1) * 100
                ev_a_net = (best_a["price"] * TAX_RATE / fair_a - 1) * 100

                if ev_h_net > ev_a_net:
                    pick, odd, fair, ev_n, b_name = home, best_h["price"], fair_h, ev_h_net, best_h["bookie"]
                else:
                    pick, odd, fair, ev_n, b_name = away, best_a["price"], fair_a, ev_a_net, best_a["bookie"]

                if ev_n >= EV_THRESHOLD and odd >= MIN_ODD and f"{m_id}_v" not in state:
                    stake = calculate_kelly_stake(odd, fair)
                    if stake > 0:
                        msg = format_value_message(sport_label, home, away, pick, odd, fair, ev_n, m_dt, stake, b_name)
                        send_msg(msg)
                        state[f"{m_id}_v"] = now.isoformat()
                        save_state(state)
                        time.sleep(1)
            except: continue

if __name__ == "__main__":
    run()
