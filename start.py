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

# Rozszerzona lista sportów dla testu
SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 PREMIER LEAGUE",
    "soccer_spain_la_liga": "🇪🇸 LA LIGA",
    "soccer_germany_bundesliga": "🇩🇪 BUNDESLIGA",
    "soccer_italy_serie_a": "🇮🇹 SERIE A",
    "soccer_poland_ekstraklasa": "🇵🇱 EKSTRAKLASA",
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
}

STATE_FILE = "sent.json"
MAX_DAYS = 3
EV_THRESHOLD = 0.0           # TEST: 0.0 (przyjmij wszystko)
MIN_BOOKS = 1                # TEST: 1 (minimum bukmacherów)
MIN_ODD = 1.10               # TEST: niski kurs
MAX_ODD = 10.0
MAX_HOURS_AHEAD = 168        # Szukaj na 7 dni w przód

BANKROLL = 1000
KELLY_FRACTION = 0.1
TAX_RATE = 0.88

# ================= POMOCNICZE =================

def load_state():
    if not os.path.exists(STATE_FILE): return {}
    try:
        with open(STATE_FILE, "r") as f: return json.load(f)
    except: return {}

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

def fair_odds(avg_h, avg_a):
    p_h, p_a = 1 / avg_h, 1 / avg_a
    total = p_h + p_a
    return 1 / (p_h / total), 1 / (p_a / total)

def send_msg(text):
    print(f"📡 Telegram Send: {text[:50]}...")
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=10)
        if r.status_code != 200: print(f"❌ Błąd Telegram: {r.text}")
    except: pass

# ================= GŁÓWNA PĘTLA =================

def run():
    print("🚀 START BOTA TESTOWEGO")
    send_msg("🤖 *Bot uruchomiony!*\nSprawdzam oferty...")
    
    if not API_KEYS:
        print("❌ Brak kluczy API w Secrets!")
        return

    state = clean_state(load_state())
    now = datetime.now(timezone.utc)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        print(f"\n🔍 SKANUJĘ: {sport_label}...")
        matches = None
        
        for key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
                params = {
                    "apiKey": key,
                    "regions": "eu,us,uk", # Rozszerzone regiony
                    "markets": "h2h",
                    "oddsFormat": "decimal"
                }
                r = requests.get(url, params=params, timeout=10)
                
                if r.status_code == 200:
                    matches = r.json()
                    print(f"✅ API OK! Znaleziono meczów: {len(matches)}")
                    break
                elif r.status_code == 429:
                    print(f"⚠️ Klucz {key[:5]}... wyczerpany (429)")
                    continue
                else:
                    print(f"❌ Błąd API ({r.status_code}): {r.text}")
            except Exception as e:
                print(f"❌ Błąd połączenia: {e}")

        if not matches:
            print(f"⏭️ Pomijam {sport_label} - brak danych.")
            continue

        for match in matches:
            try:
                m_id = match["id"]
                home = match["home_team"]
                away = match["away_team"]
                m_dt = datetime.fromisoformat(match["commence_time"].replace('Z', '+00:00'))

                # Logowanie każdego meczu w konsoli
                print(f"   Analizuję: {home} vs {away} ({m_dt.strftime('%d.%m %H:%M')})")

                if m_dt < now:
                    continue
                if m_dt > (now + timedelta(hours=MAX_HOURS_AHEAD)):
                    continue

                odds_h, odds_a = [], []
                for bm in match.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market["key"] == "h2h":
                            try:
                                h_o = next(o["price"] for o in market["outcomes"] if o["name"] == home)
                                a_o = next(o["price"] for o in market["outcomes"] if o["name"] == away)
                                odds_h.append(h_o)
                                odds_a.append(a_o)
                            except: continue

                if len(odds_h) < MIN_BOOKS:
                    continue

                avg_h, avg_a = sum(odds_h)/len(odds_h), sum(odds_a)/len(odds_a)
                fair_h, fair_a = fair_odds(avg_h, avg_a)
                max_h, max_a = max(odds_h), max(odds_a)

                ev_h = (max_h * TAX_RATE / fair_h - 1) * 100
                ev_a = (max_a * TAX_RATE / fair_a - 1) * 100

                if ev_h > ev_a:
                    pick, odd, fair, ev_n = home, max_h, fair_h, ev_h
                else:
                    pick, odd, fair, ev_n = away, max_a, fair_a, ev_a

                # Filtr testowy (pamiętaj o kluczu _t w state)
                if odd >= MIN_ODD and f"{m_id}_t" not in state:
                    msg = (
                        f"📊 *NOWA OFERTA*\n"
                        f"🏆 {sport_label}\n"
                        f"⚔️ {home} vs {away}\n"
                        f"✅ TYP: *{pick}*\n"
                        f"📈 Kurs: `{odd:.2f}`\n"
                        f"📊 EV: `{ev_n:.1f}%`"
                    )
                    send_msg(msg)
                    state[f"{m_id}_t"] = now.isoformat()
                    save_state(state)
                    time.sleep(1)
            except Exception as e:
                print(f"   ⚠️ Błąd przy meczu: {e}")
                continue

    print("\n✅ KONIEC SKANOWANIA")

if __name__ == "__main__":
    run()
