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
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def clean_state(state):
    now = datetime.now(timezone.utc)
    new_state = {}
    for key, ts in state.items():
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if now - dt <= timedelta(days=MAX_DAYS):
                new_state[key] = ts
        except Exception as e:
            print(f"Error cleaning state for {key}: {e}")
    return new_state

def calculate_kelly_stake(odd, fair_odd):
    real_odd_netto = odd * TAX_RATE
    if real_odd_netto <= 1.0:
        return 0
    p = 1 / fair_odd
    b = real_odd_netto - 1
    kelly_percent = (b * p - (1 - p)) / b
    stake = BANKROLL * kelly_percent * KELLY_FRACTION
    return max(0, round(stake, 2))

def fair_odds(avg_h, avg_d, avg_a):
    # uwzględnia remis
    p_h, p_d, p_a = 1 / avg_h, 1 / avg_d, 1 / avg_a
    total = p_h + p_d + p_a
    return 1 / (p_h / total), 1 / (p_d / total), 1 / (p_a / total)

# ================= KOMUNIKACJA =================

def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        print("Telegram token or chat ID missing!")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram send error: {e}")

def format_value_message(sport_label, home, draw, away, pick, odd, fair, ev_netto, m_dt, stake):
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

# ================= GŁÓWNA PĘTLA =================

def run():
    if not API_KEYS:
        print("No API keys configured!")
        return

    state = clean_state(load_state())
    save_state(state)
    now = datetime.now(timezone.utc)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                    params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=10
                )
                if r.status_code == 200:
                    matches = r.json()
                    break
                else:
                    print(f"API error {r.status_code} for key {key}")
            except Exception as e:
                print(f"API request error with key {key}: {e}")
                continue

        if not matches:
            continue

        for match in matches:
            try:
                m_id = match["id"]
                home = match["home_team"]
                away = match["away_team"]
                m_dt = datetime.fromisoformat(match["commence_time"].replace('Z', '+00:00'))

                if m_dt < now or m_dt > (now + timedelta(hours=MAX_HOURS_AHEAD)):
                    continue

                odds_h, odds_d, odds_a = [], [], []

                for bm in match.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market["key"] == "h2h":
                            outcomes = {o["name"]: o["price"] for o in market.get("outcomes", [])}
                            if home in outcomes:
                                odds_h.append(outcomes[home])
                            if away in outcomes:
                                odds_a.append(outcomes[away])
                            # zakładamy remis jeśli podany przez bukmachera
                            draw_val = outcomes.get("Draw")
                            if draw_val:
                                odds_d.append(draw_val)

                if len(odds_h) < 1 or len(odds_a) < 1 or len(odds_d) < 1:
                    continue  # za mało danych

                avg_h = sum(odds_h) / len(odds_h)
                avg_d = sum(odds_d) / len(odds_d)
                avg_a = sum(odds_a) / len(odds_a)

                fair_h, fair_d, fair_a = fair_odds(avg_h, avg_d, avg_a)

                max_h = max(odds_h)
                max_d = max(odds_d) if odds_d else 0
                max_a = max(odds_a)

                ev_h_net = (max_h * TAX_RATE / fair_h - 1) * 100
                ev_d_net = (max_d * TAX_RATE / fair_d - 1) * 100 if max_d else -100
                ev_a_net = (max_a * TAX_RATE / fair_a - 1) * 100

                # wybór najlepszego EV
                ev_dict = {home: ev_h_net, "Draw": ev_d_net, away: ev_a_net}
                pick, ev_n = max(ev_dict.items(), key=lambda x: x[1])
                odd = max_h if pick == home else (max_a if pick == away else max_d)
                fair = fair_h if pick == home else (fair_a if pick == away else fair_d)

                if ev_n >= EV_THRESHOLD and odd >= MIN_ODD and f"{m_id}_v" not in state:
                    stake = calculate_kelly_stake(odd, fair)
                    if stake > 0:
                        msg = format_value_message(sport_label, home, "Draw", away, pick, odd, fair, ev_n, m_dt, stake)
                        send_msg(msg)
                        state[f"{m_id}_v"] = now.isoformat()
                        save_state(state)
                        time.sleep(1)

            except Exception as e:
                print(f"Error processing match {match.get('id')}: {e}")
                continue

if __name__ == "__main__":
    run()
