import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')

# LISTA KLUCZY API
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

# ----------------- FUNKCJE -----------------

def send_msg(txt):
    if not T_TOKEN or not T_CHAT:
        print("❌ Brak tokena lub chat ID Telegrama!")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Błąd wysyłki Telegram: {e}")

def is_already_sent(match_id, category=""):
    unique_key = f"{match_id}_{category}"
    if not os.path.exists(DB_FILE):
        open(DB_FILE, 'w').close()
        return False
    with open(DB_FILE, "r") as f:
        return unique_key in f.read().splitlines()

def mark_as_sent(match_id, category=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")

def fetch_odds(sport_key):
    """Próbuje pobrać dane używając dostępnych kluczy po kolei."""
    for i, key in enumerate(API_KEYS):
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/"
        params = {'apiKey': key, 'regions': 'eu', 'markets': 'h2h'}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print(f"⚠️ Klucz nr {i+1} wyczerpany, przełączam na kolejny...")
                continue
        except requests.exceptions.RequestException:
            continue
    return None

def format_message(
    sport_label, home, away, pick_team, avg_h, avg_a, target_odd, m_dt, 
    tag="PEWNIAK", support=""
):
    """Tworzy czytelną wiadomość w Markdown dla Telegrama."""
    msg = (
        f"{tag}\n"
        f"🏆 {sport_label}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"✅ STAWIAJ NA: *{pick_team}*\n"
        f"🟢 {home}: `{avg_h:.2f}`\n"
        f"⚪ {away}: `{avg_a:.2f}`\n"
        f"📈 Kurs OKAZJA: `{target_odd:.2f}`\n"
        f"⏰ {m_dt.strftime('%d.%m %H:%M')} UTC\n"
    )
    if support:
        msg += f"🛡️ Sugerowana podpórka: {support}\n"
    msg += "━━━━━━━━━━━━━━━"
    return msg

# ----------------- GŁÓWNA FUNKCJA -----------------

def run_pro_radar():
    if not API_KEYS:
        print("❌ Brak skonfigurowanych kluczy API!")
        return

    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(days=3)

    # STATUS SYSTEMU
    if now.hour == 0 or os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        status_msg = (
            f"🟢 *STATUS: AKTYWNY*\n"
            f"✅ Liczba kluczy API: `{len(API_KEYS)}`\n"
            f"🤖 Skanowanie ofert (max 3 dni)..."
        )
        send_msg(status_msg)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        res = fetch_odds(sport_key)
        if not res: 
            continue

        for match in res:
            try:
                m_id = match['id']
                home = match['home_team']
                away = match['away_team']
                m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                if m_dt > limit_date:
                    continue

                all_h, all_a = [], []
                for bm in match.get('bookmakers', []):
                    for market in bm.get('markets', []):
                        if market.get('key') == 'h2h':
                            try:
                                h_o = next(o['price'] for o in market['outcomes'] if o['name'] == home)
                                a_o = next(o['price'] for o in market['outcomes'] if o['name'] == away)
                                all_h.append(h_o)
                                all_a.append(a_o)
                            except (StopIteration, KeyError):
                                continue

                if not all_h:
                    continue

                avg_h, avg_a = sum(all_h)/len(all_h), sum(all_a)/len(all_a)
                max_h, max_a = max(all_h), max(all_a)

                # 1. BUKMACHER ZASPAŁ (VALUE BET)
                if (max_h > avg_h * 1.12 or max_a > avg_a * 1.12) and not is_already_sent(m_id, "value"):
                    target = home if max_h > avg_h * 1.12 else away
                    target_odd = max_h if max_h > avg_h * 1.12 else max_a
                    avg_val = avg_h if max_h > avg_h * 1.12 else avg_a

                    v_msg = format_message(
                        sport_label=sport_label,
                        home=home,
                        away=away,
                        pick_team=target,
                        avg_h=avg_h,
                        avg_a=avg_a,
                        target_odd=target_odd,
                        m_dt=m_dt,
                        tag="💎 BUKMACHER ZASPAŁ! 💎"
                    )
                    send_msg(v_msg)
                    mark_as_sent(m_id, "value")

                # 2. PEWNIAKI
                min_avg = min(avg_h, avg_a)
                if min_avg <= 1.75 and not is_already_sent(m_id, "daily"):
                    tag = "🔥 PEWNIAK" if min_avg <= 1.35 else "⭐ WARTE UWAGI"
                    pick_team = home if avg_h < avg_a else away
                    support = "1X/X2" if "⚽" in sport_label and min_avg > 1.40 else ""

                    daily_msg = format_message(
                        sport_label=sport_label,
                        home=home,
                        away=away,
                        pick_team=pick_team,
                        avg_h=avg_h,
                        avg_a=avg_a,
                        target_odd=min(avg_h, avg_a),
                        m_dt=m_dt,
                        tag=tag,
                        support=support
                    )
                    send_msg(daily_msg)
                    mark_as_sent(m_id, "daily")

            except Exception as e:
                print(f"⚠️ Błąd przetwarzania meczu: {e}")
            time.sleep(1)

# ----------------- URUCHOMIENIE -----------------

if __name__ == "__main__":
    run_pro_radar()
