import requests
import os
import time
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================

T_TOKEN = os.getenv("T_TOKEN")  # Token Twojego bota Telegram
T_CHAT = os.getenv("T_CHAT")    # ID Twojego czatu/kanału

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

# --- PARAMETRY STRATEGII ---
STATE_FILE = "sent.json"
MAX_DAYS = 3            # Czyści stare mecze
EV_THRESHOLD = 3.0      # % EV netto (po podatku), przy którym wysyłamy sygnał
PEWNIAK_EV_THRESHOLD = 7.0  # % EV netto dla oznaczenia "Pewniak"
PEWNIAK_MAX_ODD = 2.60  # Maksymalny kurs dla pewniaka (bezpieczeństwo)
MIN_ODD = 1.55          # Minimalny kurs brutto
MAX_HOURS_AHEAD = 45    # Jak daleko w przyszłość szukać meczów

# --- ZARZĄDZANIE KAPITAŁEM ---
BANKROLL = 1000         # Twój budżet w PLN
KELLY_FRACTION = 0.2    # 20% stawki Kelly'ego (bezpieczne podejście)
TAX_RATE = 0.88         # Uwzględnienie 12% podatku w Polsce

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
    now = datetime.now(timezone.utc)
    new_state = {}
    for key, ts in state.items():
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        except ValueError:
            continue
        if now - dt <= timedelta(days=MAX_DAYS):
            new_state[key] = ts
    return new_state

# ================= MATEMATYKA I LOGIKA =================

def calculate_kelly_stake(odd, fair_odd):
    """Oblicza stawkę Kelly'ego uwzględniając podatek 12%"""
    real_odd_netto = odd * TAX_RATE
    if real_odd_netto <= 1.0:
        return 0
    
    p = 1 / fair_odd
    q = 1 - p
    b = real_odd_netto - 1
    
    kelly_percent = (b * p - q) / b
    final_percent = kelly_percent * KELLY_FRACTION
    
    stake = BANKROLL * final_percent
    return max(0, round(stake, 2))

def fair_odds(avg_h, avg_a):
    """Oblicza kursy sprawiedliwe usuwając marżę (dla rynków 2-drogowych)"""
    p_h = 1 / avg_h
    p_a = 1 / avg_a
    total = p_h + p_a
    return 1 / (p_h / total), 1 / (p_a / total)

def ev_percent(odd, fair):
    return (odd / fair - 1) * 100

# ================= KOMUNIKACJA =================

def send_msg(text):
    if not T_TOKEN or not T_CHAT:
        print("Błąd: Brak T_TOKEN lub T_CHAT")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": T_CHAT,
            "text": text,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        print(f"Błąd wysyłania do Telegrama: {e}")

def format_value_message(sport_label, home, away, pick, odd, fair, ev_netto, m_dt, stake):
    is_pewniak = ev_netto >= PEWNIAK_EV_THRESHOLD and odd <= PEWNIAK_MAX_ODD
    header = "🔥 💎 **PEWNIAK (+EV)** 🔥" if is_pewniak else "💎 *VALUE (+EV)*"
    pick_icon = "⭐" if is_pewniak else "✅"
    
    msg = (
        f"{header}\n"
        f"🏆 {sport_label}\n"
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
        print("Błąd: Brak kluczy API!")
        return

    state = clean_state(load_state())
    save_state(state)
    
    now = datetime.now(timezone.utc)
    limit_dt = now + timedelta(hours=MAX_HOURS_AHEAD)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        print(f"Sprawdzam: {sport_label}...")
        
        # Rotacja kluczy API
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                    params={"apiKey": key, "regions": "eu", "markets": "h2h"},
                    timeout=10
                )
                if r.status_code == 200:
                    matches = r.json()
                    break
            except: continue
        
        if not matches: continue

        for match in matches:
            try:
                m_id = match["id"]
                home, away = match["home_team"], match["away_team"]
                m_dt = datetime.fromisoformat(match["commence_time"].replace('Z', '+00:00'))

                if m_dt < now or m_dt > limit_dt:
                    continue

                all_h, all_a = [], []

                for bm in match.get("bookmakers", []):
                    for market in bm.get("markets", []):
                        if market.get("key") != "h2h": continue
                        try:
                            h = next(o["price"] for o in market["outcomes"] if o["name"] == home)
                            a = next(o["price"] for o in market["outcomes"] if o["name"] == away)
                            all_h.append(h)
                            all_a.append(a)
                        except StopIteration: continue

                if len(all_h) < 3: continue # Minimum 3 bukmacherów do średniej

                avg_h, avg_a = sum(all_h)/len(all_h), sum(all_a)/len(all_a)
                max_h, max_a = max(all_h), max(all_a)

                fair_h, fair_a = fair_odds(avg_h, avg_a)
                
                # Obliczanie EV Netto (po podatku 12%)
                ev_h_netto = ev_percent(max_h * TAX_RATE, fair_h)
                ev_a_netto = ev_percent(max_a * TAX_RATE, fair_a)

                # Wybór lepszej okazji
                if ev_h_netto > ev_a_netto:
                    pick, odd, fair, ev_netto = home, max_h, fair_h, ev_h_netto
                else:
                    pick, odd, fair, ev_netto = away, max_a, fair_a, ev_a_netto

                # Filtry końcowe
                if ev_netto < EV_THRESHOLD or odd < MIN_ODD:
                    continue
                
                if f"{m_id}_value" in state:
                    continue

                stake = calculate_kelly_stake(odd, fair)
                if stake <= 0: continue

                msg = format_value_message(sport_label, home, away, pick, odd, fair, ev_netto, m_dt, stake)
                send_msg(msg)
                
                state[f"{m_id}_value"] = now.isoformat()
                save_state(state)
                time.sleep(1) # Anty-spam

            except Exception as e:
                print(f"⚠️ Błąd przy meczu {match.get('id')}: {e}")

if __name__ == "__main__":
    run()
