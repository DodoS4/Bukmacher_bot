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
MAX_DAYS = 3        # Czyści stare mecze
EV_THRESHOLD = 4.0  # % EV
MIN_ODD = 1.55
MAX_HOURS_AHEAD = 45

# ================= STATE (JSON + auto-clean) =================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def clean_state(state):
    """Usuwa mecze starsze niż MAX_DAYS dni"""
    now = datetime.now(timezone.utc)
    new_state = {}
    for key, ts in state.items():
        try:
            # Poprawione dla ISO z Z na końcu
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        except ValueError:
            try:
                dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        if now - dt <= timedelta(days=MAX_DAYS):
            new_state[key] = ts
    return new_state

state = load_state()
state = clean_state(state)
save_state(state)

def is_already_sent(match_id, category):
    return f"{match_id}_{category}" in state

def mark_as_sent(match_id, category):
    key = f"{match_id}_{category}"
    state[key] = datetime.now(timezone.utc).isoformat() + "Z"
    save_state(state)

# ================= TELEGRAM =================

def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": T_CHAT,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=10)
    except requests.exceptions.RequestException:
        pass

# ================= ODDS API =================

def fetch_odds(sport_key):
    for key in API_KEYS:
        try:
            r = requests.get(
                f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                params={"apiKey": key, "regions": "eu", "markets": "h2h"},
                timeout=10
            )
            if r.status_code == 200:
                return r.json()
        except requests.exceptions.RequestException:
            continue
    return None

# ================= EV =================

def fair_odds(avg_h, avg_a):
    p_h = 1 / avg_h
    p_a = 1 / avg_a
    total = p_h + p_a
    return 1 / (p_h / total), 1 / (p_a / total)

def ev_percent(odd, fair):
    return (odd / fair - 1) * 100

# ================= FORMAT =================

def format_value_message(sport_label, home, away, pick, odd, fair, ev, m_dt):
    """Tworzy czytelny komunikat Value/EV dla Telegrama"""
    pick_icon = "✅"
    msg = (
        f"💎 *VALUE (+EV)*\n"
        f"🏆 {sport_label}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"{pick_icon} STAWIAJ NA: *{pick}*\n"
        f"🔹 {home}: `{fair if pick==home else ''}`\n"
        f"🔹 {away}: `{fair if pick==away else ''}`\n"
        f"📈 Kurs: `{odd:.2f}`\n"
        f"🔥 EV: `+{ev:.1f}%`\n"
        f"⏰ {m_dt.strftime('%d.%m %H:%M')} UTC\n"
        f"━━━━━━━━━━━━━━━"
    )
    return msg

# ================= GŁÓWNA LOGIKA =================

def run():
    if not API_KEYS:
        return

    now = datetime.now(timezone.utc)
    limit_dt = now + timedelta(hours=MAX_HOURS_AHEAD)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = fetch_odds(sport_key)
        if not matches:
            continue

        for match in matches:
            try:
                m_id = match["id"]
                home, away = match["home_team"], match["away_team"]
                m_dt = datetime.strptime(
                    match["commence_time"], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)

                if m_dt > limit_dt:
                    continue

                all_h, all_a = [], []

                for bm in match.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market.get("key") != "h2h":
                            continue
                        try:
                            h = next(o["price"] for o in market["outcomes"] if o["name"] == home)
                            a = next(o["price"] for o in market["outcomes"] if o["name"] == away)
                            all_h.append(h)
                            all_a.append(a)
                        except StopIteration:
                            continue

                if len(all_h) < 2:
                    continue  # mniejsze ligi też bierzemy

                avg_h, avg_a = sum(all_h)/len(all_h), sum(all_a)/len(all_a)
                max_h, max_a = max(all_h), max(all_a)

                fair_h, fair_a = fair_odds(avg_h, avg_a)
                ev_h, ev_a = ev_percent(max_h, fair_h), ev_percent(max_a, fair_a)

                if ev_h < EV_THRESHOLD and ev_a < EV_THRESHOLD:
                    continue

                if ev_h > ev_a:
                    pick, odd, fair, ev = home, max_h, fair_h, ev_h
                else:
                    pick, odd, fair, ev = away, max_a, fair_a, ev_a

                if odd < MIN_ODD or is_already_sent(m_id, "value"):
                    continue

                msg = format_value_message(sport_label, home, away, pick, odd, fair, ev, m_dt)
                send_msg(msg)
                mark_as_sent(m_id, "value")

                time.sleep(0.5)

            except Exception as e:
                print(f"⚠️ Błąd przy meczu {match.get('id', 'unknown')}: {e}")
                continue

# ================= START =================

if __name__ == "__main__":
    run()