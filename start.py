import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIG =================

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")

API_KEYS = [k for k in [
    os.getenv("ODDS_KEY"),
    os.getenv("ODDS_KEY_2"),
    os.getenv("ODDS_KEY_3"),
] if k]

SPORTS_CONFIG = {
    "soccer_epl": ("⚽ PREMIER LEAGUE", 3),
    "soccer_spain_la_liga": ("⚽ LA LIGA", 3),
    "soccer_germany_bundesliga": ("⚽ BUNDESLIGA", 3),
    "soccer_italy_serie_a": ("⚽ SERIE A", 3),
    "soccer_poland_ekstraklasa": ("⚽ EKSTRAKLASA", 3),
    "basketball_nba": ("🏀 NBA", 2),
    "icehockey_nhl": ("🏒 NHL", 2),
}

STATE_FILE = "sent.json"

# === FILTRY ===
MIN_ODD = 1.55
MAX_ODD = 6.00
MAX_HOURS_AHEAD = 48

# === EV ===
EV_THRESHOLD = 3.0
PEWNIAK_EV = 7.0
PEWNIAK_MAX_ODD = 2.60

# === BANKROLL ===
BANKROLL = 1000
KELLY_FRACTION = 0.2
MAX_STAKE_PCT = 0.05
TAX_RATE = 0.88

# ================= STATE =================

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# ================= MATEMATYKA =================

def fair_odds(odds):
    probs = [1 / o for o in odds]
    total = sum(probs)
    return [1 / (p / total) for p in probs]

def ev_netto(odd, fair):
    return (odd * TAX_RATE / fair - 1) * 100

def kelly_stake(odd, fair):
    b = odd * TAX_RATE - 1
    if b <= 0:
        return 0
    p = 1 / fair
    k = (b * p - (1 - p)) / b
    stake = BANKROLL * k * KELLY_FRACTION
    stake = max(0, stake)
    return round(min(stake, BANKROLL * MAX_STAKE_PCT), 2)

# ================= TELEGRAM =================

def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={
                "chat_id": T_CHAT,
                "text": text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    except:
        pass

def format_msg(label, home, away, pick, odd, fair, ev, stake, dt):
    pewniak = ev >= PEWNIAK_EV and odd <= PEWNIAK_MAX_ODD
    header = "🔥💎 **PEWNIAK (+EV)**" if pewniak else "💎 *VALUE (+EV)*"
    icon = "⭐" if pewniak else "✅"

    return (
        f"{header}\n"
        f"🏆 {label}\n"
        f"⚔️ **{home} vs {away}**\n"
        f"━━━━━━━━━━━━━━\n"
        f"{icon} *{pick}*\n"
        f"📈 Kurs: `{odd:.2f}` (Fair: {fair:.2f})\n"
        f"🔥 EV netto: `+{ev:.1f}%`\n"
        f"💰 Stawka: *{stake} zł*\n"
        f"⏰ {dt.strftime('%d.%m %H:%M')} UTC\n"
        f"━━━━━━━━━━━━━━"
    )

# ================= GŁÓWNA LOGIKA =================

def run():
    state = load_state()
    now = datetime.now(timezone.utc)

    for sport, (label, outcomes_count) in SPORTS_CONFIG.items():
        matches = None

        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport}/odds/",
                    params={
                        "apiKey": key,
                        "regions": "eu",
                        "markets": "h2h",
                    },
                    timeout=10,
                )
                if r.status_code == 200:
                    matches = r.json()
                    break
            except:
                continue

        if not matches:
            continue

        for m in matches:
            m_dt = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
            if m_dt < now or m_dt > now + timedelta(hours=MAX_HOURS_AHEAD):
                continue

            home = m["home_team"]
            away = m["away_team"]

            best = {}
            for b in m["bookmakers"]:
                for o in b["markets"][0]["outcomes"]:
                    name = o["name"]
                    best[name] = max(best.get(name, 0), o["price"])

            if len(best) != outcomes_count:
                continue

            odds = list(best.values())
            fair = fair_odds(odds)

            for (pick, odd), f in zip(best.items(), fair):
                if odd < MIN_ODD or odd > MAX_ODD:
                    continue

                ev = ev_netto(odd, f)
                if ev < EV_THRESHOLD:
                    continue

                key_id = f"{sport}_{home}_{away}_{pick}"
                if key_id in state:
                    continue

                stake = kelly_stake(odd, f)
                if stake <= 0:
                    continue

                send_msg(format_msg(label, home, away, pick, odd, f, ev, stake, m_dt))
                state[key_id] = m_dt.isoformat()

    save_state(state)

# ================= RUN =================

if __name__ == "__main__":
    run()
