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

# --- PARAMETRY ZAROBKOWE ---
STATE_FILE = "sent.json"
MAX_DAYS = 3            
EV_THRESHOLD = 3.0      # Szukamy tylko realnego zysku powyżej 3%
MIN_ODD = 1.55          # Kursy poniżej 1.55 są mało opłacalne przy podatku 12%
MAX_HOURS_AHEAD = 48    
BANKROLL = 1000         # Twój budżet (zmień tę kwotę według uznania)
KELLY_FRACTION = 0.2    # Agresywność stawkowania (0.2 jest bezpieczne)
TAX_RATE = 0.88         # Polski podatek (12%)

# ================= POMOCNICZE =================

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {}

def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f: json.dump(state, f, indent=4)
    except: pass

def get_fair_odds(odds_list):
    probs = [1/o for o in odds_list]
    total_prob = sum(probs)
    return [1 / (p / total_prob) for p in probs]

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except: pass

# ================= LOGIKA ZAROBKOWA =================

def run():
    state = load_state()
    now = datetime.now(timezone.utc)
    
    # Czyszczenie starych meczów z bazy (starsze niż 3 dni)
    state = {k: v for k, v in state.items() if (now - datetime.fromisoformat(v['time'] if isinstance(v, dict) else v)).days < MAX_DAYS}

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                    params={"apiKey": key, "regions": "eu", "markets": "h2h"},
                    timeout=15
                )
                if r.status_code == 200:
                    matches = r.json()
                    break
                elif r.status_code == 429: continue
            except: continue
        
        if not matches: continue

        for match in matches:
            try:
                m_id = match["id"]
                # BLOKADA DUPLIKATÓW - wysyłaj tylko nowe mecze
                if f"{m_id}_v" in state: continue 

                home, away = match["home_team"], match["away_team"]
                m_dt = datetime.fromisoformat(match["commence_time"].replace('Z', '+00:00'))

                if m_dt < now or m_dt > (now + timedelta(hours=MAX_HOURS_AHEAD)): continue

                all_odds = {"h": [], "d": [], "a": []}
                for bm in match.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market["key"] == "h2h":
                            outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                            if home in outcomes and away in outcomes:
                                all_odds["h"].append(outcomes[home])
                                all_odds["a"].append(outcomes[away])
                                if "Draw" in outcomes: all_odds["d"].append(outcomes["Draw"])

                if len(all_odds["h"]) < 3: continue 

                avg_h = sum(all_odds["h"]) / len(all_odds["h"])
                avg_a = sum(all_odds["a"]) / len(all_odds["a"])
                
                if all_odds["d"]:
                    avg_d = sum(all_odds["d"]) / len(all_odds["d"])
                    fair_h, fair_d, fair_a = get_fair_odds([avg_h, avg_d, avg_a])
                else:
                    fair_h, fair_a = get_fair_odds([avg_h, avg_a])

                max_h, max_a = max(all_odds["h"]), max(all_odds["a"])
                ev_h = (max_h * TAX_RATE / fair_h - 1) * 100
                ev_a = (max_a * TAX_RATE / fair_a - 1) * 100

                if ev_h > ev_a:
                    pick, odd, fair, ev = home, max_h, fair_h, ev_h
                else:
                    pick, odd, fair, ev = away, max_a, fair_a, ev_a

                # FILTR ZYSKU
                if ev >= EV_THRESHOLD and odd >= MIN_ODD:
                    # Obliczanie stawki Kelly'ego
                    p = 1 / fair
                    b = (odd * TAX_RATE) - 1
                    kelly_pc = (b * p - (1 - p)) / b
                    stake = max(0, round(BANKROLL * kelly_pc * KELLY_FRACTION, 2))

                    if stake > 2: # Wysyłaj tylko jeśli stawka ma sens ekonomiczny
                        msg = (
                            f"🔥 **OKAZJA VALUE (+EV)**\n"
                            f"🏆 {sport_label}\n"
                            f"⚔️ **{home} vs {away}**\n"
                            f"━━━━━━━━━━━━━━━\n"
                            f"✅ TYP: *{pick}*\n"
                            f"📈 Kurs: `{odd:.2f}` (Fair: {fair:.2f})\n"
                            f"🔥 EV netto: `+{ev:.1f}%`\n"
                            f"💰 Sugerowana stawka: *{stake} zł*\n"
                            f"⏰ Start: {m_dt.strftime('%d.%m %H:%M')} UTC\n"
                            f"━━━━━━━━━━━━━━━"
                        )
                        send_msg(msg)
                        state[f"{m_id}_v"] = {"time": now.isoformat(), "pick": pick}
                        save_state(state)
                        time.sleep(1)
            except: continue

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"Błąd: {e}")
