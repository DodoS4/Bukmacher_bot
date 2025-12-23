import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')

KEYS_POOL = [
    os.getenv('ODDS_KEY'),
    os.getenv('ODDS_KEY_2'),
    os.getenv('ODDS_KEY_3'),
    os.getenv('ODDS_KEY_4')
]
API_KEYS = [k for k in KEYS_POOL if k]

SPORTS_CONFIG = {
    'soccer_epl': '⚽ PREMIER LEAGUE',
    'soccer_spain_la_liga': '⚽ LA LIGA',
    'soccer_germany_bundesliga': '⚽ BUNDESLIGA',
    'soccer_italy_serie_a': '⚽ SERIE A',
    'soccer_poland_ekstraklasa': '⚽ EKSTRAKLASA',
    'basketball_nba': '🏀 NBA',
    'icehockey_nhl': '🏒 NHL',
    'mma_mixed_martial_arts': '🥊 MMA/UFC'
}

DB_FILE = "sent_matches.txt"


# --- FUNKCJE ---
def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Telegram error:", e)


def is_already_sent(match_id, category=""):
    key = f"{match_id}_{category}"
    if not os.path.exists(DB_FILE):
        open(DB_FILE, 'w').close()
        return False
    with open(DB_FILE, "r") as f:
        return key in f.read().splitlines()


def mark_as_sent(match_id, category=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")


def fetch_odds(sport_key):
    for i, key in enumerate(API_KEYS):
        url = (
            f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
            f"?apiKey={key}&regions=eu&markets=h2h"
        )
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
            elif r.status_code == 429:
                print(f"⚠️ Klucz {i+1} limit – przełączam")
        except Exception as e:
            print("API error:", e)
    return None


def calculate_ev(avg_odds, best_odds):
    implied_prob = 1 / avg_odds
    return (best_odds * implied_prob) - 1


# --- GŁÓWNA LOGIKA ---
def run_pro_radar():
    if not API_KEYS:
        print("❌ Brak kluczy API")
        return

    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(days=3)

    # STATUS
    if now.hour == 0 or os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        send_msg(
            f"🟢 *STATUS: AKTYWNY*\n"
            f"🔑 Klucze API: `{len(API_KEYS)}`\n"
            f"🔍 Szukam 3 SUPER OKAZJI (EV+)"
        )

    super_values = []

    for sport_key, sport_label in SPORTS_CONFIG.items():
        data = fetch_odds(sport_key)
        if not data:
            continue

        for match in data:
            try:
                m_id = match['id']
                home = match['home_team']
                away = match['away_team']
                m_dt = datetime.strptime(
                    match['commence_time'], "%Y-%m-%dT%H:%M:%SZ"
                ).replace(tzinfo=timezone.utc)
            except:
                continue

            if m_dt > limit_date:
                continue

            all_h, all_a = [], []

            for bm in match.get('bookmakers', []):
                for market in bm.get('markets', []):
                    if market.get('key') == 'h2h' and len(market.get('outcomes', [])) == 2:
                        try:
                            h = next(o['price'] for o in market['outcomes'] if o['name'] == home)
                            a = next(o['price'] for o in market['outcomes'] if o['name'] == away)
                            all_h.append(h)
                            all_a.append(a)
                        except:
                            continue

            if len(all_h) < 4:
                continue

            avg_h, avg_a = sum(all_h) / len(all_h), sum(all_a) / len(all_a)
            max_h, max_a = max(all_h), max(all_a)

            ev_h = calculate_ev(avg_h, max_h)
            ev_a = calculate_ev(avg_a, max_a)

            if ev_h > ev_a:
                ev, pick, odds, avg = ev_h, home, max_h, avg_h
            else:
                ev, pick, odds, avg = ev_a, away, max_a, avg_a

            if ev >= 0.08:
                super_values.append({
                    "id": m_id,
                    "sport": sport_label,
                    "pick": pick,
                    "odds": odds,
                    "avg": avg,
                    "ev": ev,
                    "time": m_dt
                })

        time.sleep(1)

    # --- TOP 3 SUPER OKAZJE ---
    top3 = sorted(super_values, key=lambda x: x['ev'], reverse=True)[:3]

    for i, bet in enumerate(top3, start=1):
        if is_already_sent(bet['id'], "super"):
            continue

        msg = (
            f"🚀 *SUPER OKAZJA #{i}*\n"
            f"🏆 {bet['sport']}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"✅ STAWIAJ NA: *{bet['pick'].upper()}*\n\n"
            f"💰 Kurs: `{bet['odds']:.2f}`\n"
            f"📊 Średnia rynku: `{bet['avg']:.2f}`\n"
            f"📈 EV: `+{bet['ev']*100:.1f}%`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⏰ `{bet['time'].strftime('%d.%m %H:%M')}` UTC"
        )

        send_msg(msg)
        mark_as_sent(bet['id'], "super")


if __name__ == "__main__":
    run_pro_radar()
