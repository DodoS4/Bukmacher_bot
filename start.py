import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
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
EV_THRESHOLD = 3.0           # ZMIENIONO Z 3.5 NA 3.0
MIN_ODD = 1.40               
MAX_ODD = 4.50               
TAX_RATE = 0.88              
KELLY_FRACTION = 0.1         

# ================= SYSTEM CZASU =================

def is_poland_dst():
    now = datetime.now(timezone.utc)
    dst_start = datetime(now.year, 3, 31, 1, tzinfo=timezone.utc)
    dst_start -= timedelta(days=(dst_start.weekday() + 1) % 7)
    dst_end = datetime(now.year, 10, 31, 1, tzinfo=timezone.utc)
    dst_end -= timedelta(days=(dst_end.weekday() + 1) % 7)
    return dst_start <= now < dst_end

def get_poland_hour():
    offset = 2 if is_poland_dst() else 1
    return (datetime.now(timezone.utc) + timedelta(hours=offset)).hour

# ================= DANE I KOMUNIKACJA =================

def load_data(file):
    if not os.path.exists(file): return {} if "sent" in file else []
    try:
        with open(file, "r") as f:
            data = json.load(f)
            return data if data else ([] if "history" in file else {})
    except: return {} if "sent" in file else []

def save_data(file, data):
    with open(file, "w") as f: json.dump(data, f)

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                      json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except: pass

# ================= ROZLICZENIA =================

def fetch_score(sport_key, event_id):
    for key in API_KEYS:
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/", 
                             params={"apiKey": key, "daysFrom": 3}, timeout=10)
            if r.status_code == 200:
                for s in r.json():
                    if s["id"] == event_id and s["completed"]:
                        h_score = int(next(item["score"] for item in s["scores"] if item["name"] == s["home_team"]))
                        a_score = int(next(item["score"] for item in s["scores"] if item["name"] == s["away_team"]))
                        return h_score, a_score
            elif r.status_code == 429: continue 
        except: continue
    return None

def check_results():
    history = load_data(HISTORY_FILE)
    if not history: return
    now = datetime.now(timezone.utc)
    updated_history = []
    for bet in history:
        m_dt = datetime.fromisoformat(bet["date"])
        if bet.get("status") == "pending" and now > (m_dt + timedelta(hours=4)):
            result = fetch_score(bet["sport"], bet["id"])
            if result:
                h_s, a_s = result
                is_win = (bet["pick"] == bet["home"] and h_s > a_s) or (bet["pick"] == bet["away"] and a_s > h_s)
                profit = round((bet["stake"] * bet["odd"] * TAX_RATE) - bet["stake"], 2) if is_win else -bet["stake"]
                send_msg(f"{'✅ WYGRANA' if is_win else '❌ PRZEGRANA'}\n\n🏟 {bet['home']} {h_s}:{a_s} {bet['away']}\n🎯 Typ: **{bet['pick'].upper()}**\n💰 Profit: `{profit} zł`")
                bet["status"] = "settled"
        if m_dt > (now - timedelta(days=7)): updated_history.append(bet)
    save_data(HISTORY_FILE, updated_history)

# ================= MATEMATYKA =================

def calculate_fair_odds(odds_h, odds_a, odds_d=None):
    avg_h = sum(odds_h)/len(odds_h)
    avg_a = sum(odds_a)/len(odds_a)
    if odds_d and len(odds_d) > 0:
        avg_d = sum(odds_d)/len(odds_d)
        p_total = (1/avg_h) + (1/avg_a) + (1/avg_d)
        return 1/((1/avg_h)/p_total), 1/((1/avg_a)/p_total)
    p_total = (1/avg_h) + (1/avg_a)
    return 1/((1/avg_h)/p_total), 1/((1/avg_a)/p_total)

def calculate_kelly_stake(odd, fair_odd):
    real_odd_netto = odd * TAX_RATE
    if real_odd_netto <= 1.0: return 0
    p = 1 / fair_odd
    b = real_odd_netto - 1
    kelly_percent = (b * p - (1 - p)) / b
    return max(0, round(BANKROLL * kelly_percent * KELLY_FRACTION, 2))

# ================= GŁÓWNA PĘTLA =================

def run():
    pol_hour = get_poland_hour()
    print(f"--- SESJA START (PL: {pol_hour}:00) ---")
    
    if pol_hour == 7: 
        check_results()

    state = load_data(STATE_FILE)
    history = load_data(HISTORY_FILE)
    now = datetime.now(timezone.utc)
    total_scanned, opportunities_found, active_leagues = 0, 0, 0

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                                 params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=10)
                if r.status_code == 200:
                    matches = r.json()
                    active_leagues += 1
                    break
            except: continue

        if not matches: continue
        total_scanned += len(matches)

        for m in matches:
            m_id, home, away = m["id"], m["home_team"], m["away_team"]
            m_dt = datetime.fromisoformat(m["commence_time"].replace('Z', '+00:00'))
            if m_dt < now or m_dt > (now + timedelta(hours=48)) or m_id in state: continue

            o_h, o_a, o_d = [], [], []
            for bm in m.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        try:
                            h = next(o["price"] for o in market["outcomes"] if o["name"] == home)
                            a = next(o["price"] for o in market["outcomes"] if o["name"] == away)
                            d = next((o["price"] for o in market["outcomes"] if o["name"] == "Draw"), None)
                            o_h.append(h); o_a.append(a)
                            if d: o_d.append(d)
                        except: continue

            if len(o_h) < 4: continue
            f_h, f_a = calculate_fair_odds(o_h, o_a, o_d)
            max_h, max_a = max(o_h), max(o_a)
            ev_h, ev_a = (max_h * TAX_RATE / f_h - 1) * 100, (max_a * TAX_RATE / f_a - 1) * 100
            pick, odd, fair, ev_n = (home, max_h, f_h, ev_h) if ev_h > ev_a else (away, max_a, f_a, ev_a)

            if ev_n >= EV_THRESHOLD and MIN_ODD <= odd <= MAX_ODD:
                final_stake = calculate_kelly_stake(odd, fair)
                if final_stake >= 2.0:
                    opportunities_found += 1
                    header = "🥇 GOLD" if ev_n >= 10 else "👑 PREMIUM" if ev_n >= 7 else "🟢 STANDARD"
                    msg = f"{header}\n\n🏆 {sport_label}\n⚔️ **{home}** vs **{away}**\n📍 TYP: **{pick.upper()}**\n📈 KURS: `{odd:.2f}`\n📊 EV: `+{ev_n:.1f}%` netto\n💵 STAWKA: **{final_stake} zł**"
                    send_msg(msg)
                    state[m_id] = now.isoformat()
                    history.append({"id": m_id, "home": home, "away": away, "pick": pick, "odd": odd, "stake": final_stake, "date": m_dt.isoformat(), "status": "pending", "sport": sport_key})

    if opportunities_found == 0:
        send_msg(f"ℹ️ **Status bota ({pol_hour}:00)**\nPrzeanalizowano: `{total_scanned}` meczów\nAktywne ligi: `{active_leagues}/{len(SPORTS_CONFIG)}`\nWynik: Brak okazji > {EV_THRESHOLD}%")

    save_data(STATE_FILE, state)
    save_data(HISTORY_FILE, history)
    print("--- KONIEC SESJI ---")

if __name__ == "__main__":
    run()
