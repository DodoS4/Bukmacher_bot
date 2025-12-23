import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')

# Pobieranie kluczy API
KEYS_POOL = [
    os.getenv('ODDS_KEY'),
    os.getenv('ODDS_KEY_2'),
    os.getenv('ODDS_KEY_3'),
    os.getenv('ODDS_KEY_4')
]
API_KEYS = [k for k in KEYS_POOL if k]

# USUNIĘTO MMA Z KONFIGURACJI
SPORTS_CONFIG = {
    'soccer_epl': '⚽ PREMIER LEAGUE',
    'soccer_spain_la_liga': '⚽ LA LIGA',
    'soccer_germany_bundesliga': '⚽ BUNDESLIGA',
    'soccer_italy_serie_a': '⚽ SERIE A',
    'soccer_poland_ekstraklasa': '⚽ EKSTRAKLASA',
    'basketball_nba': '🏀 NBA',
    'icehockey_nhl': '🏒 NHL'
}

DB_FILE = "sent_matches.txt"

def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def is_already_sent(match_id, category=""):
    unique_key = f"{match_id}_{category}"
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, 'w'): pass
        return False
    with open(DB_FILE, "r") as f:
        return unique_key in f.read().splitlines()

def mark_as_sent(match_id, category=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")

def fetch_odds(sport_key):
    for i, key in enumerate(API_KEYS):
        url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={key}&regions=eu&markets=h2h"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                continue
        except:
            continue
    return None

def run_pro_radar():
    if not API_KEYS: 
        print("❌ Brak kluczy API!")
        return
        
    now = datetime.now(timezone.utc)
    limit_date = now + timedelta(days=3)
    
    if os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        send_msg("🚀 *Radar uruchomiony ręcznie...* Skanuję rynek!")

    for sport_key, sport_label in SPORTS_CONFIG.items():
        res = fetch_odds(sport_key)
        if not res: continue

        for match in res:
            m_id = match['id']
            home = match['home_team']
            away = match['away_team']
            m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

            if m_dt > limit_date: continue

            all_h, all_a, all_d = [], [], []
            for bm in match['bookmakers']:
                for market in bm['markets']:
                    if market['key'] == 'h2h':
                        try:
                            h_o = next(o['price'] for o in market['outcomes'] if o['name'] == home)
                            a_o = next(o['price'] for o in market['outcomes'] if o['name'] == away)
                            all_h.append(h_o)
                            all_a.append(a_o)
                            draw_o = next((o['price'] for o in market['outcomes'] if o['name'].lower() == 'draw'), None)
                            if draw_o: all_d.append(draw_o)
                        except: continue

            if not all_h or not all_a: continue
            
            avg_h, avg_a = sum(all_h)/len(all_h), sum(all_a)/len(all_a)
            max_h, max_a = max(all_h), max(all_a)
            max_d = max(all_d) if all_d else None

            # --- 1. SUPER OKAZJA: SUREBET ---
            if max_d:
                margin = (1/max_h) + (1/max_a) + (1/max_d)
            else:
                margin = (1/max_h) + (1/max_a)

            if margin < 0.99 and not is_already_sent(m_id, "surebet"):
                profit = (1 - margin) * 100
                s_msg = f"🚀 *SUPER OKAZJA: SUREBET!* 🚀\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n💰 Zysk: `+{profit:.2f}%` (bez ryzyka)\n\n🏠 1: `{max_h:.2f}`\n✈️ 2: `{max_a:.2f}`"
                if max_d: s_msg += f"\n🤝 X: `{max_d:.2f}`"
                s_msg += f"\n━━━━━━━━━━━━━━━\n⏰ `{m_dt.strftime('%d.%m %H:%M')}` UTC"
                send_msg(s_msg)
                mark_as_sent(m_id, "surebet")

            # --- 2. SUPER OKAZJA: MEGA VALUE (+25%) ---
            elif (max_h > avg_h * 1.25 or max_a > avg_a * 1.25) and not is_already_sent(m_id, "mega"):
                target = home if max_h > avg_h * 1.25 else away
                v_k = max_h if max_h > avg_h * 1.25 else max_a
                v_avg = avg_h if max_h > avg_h * 1.25 else avg_a
                m_msg = f"🔥 *SUPER OKAZJA: MEGA VALUE!* 🔥\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n✅ POTĘŻNY BŁĄD: *{target.upper()}*\n\n📈 Kurs: `{v_k:.2f}`\n📊 Średnia: `{v_avg:.2f}`\n━━━━━━━━━━━━━━━"
                send_msg(m_msg)
                mark_as_sent(m_id, "mega")

            # --- 3. STANDARDOWY VALUE BET (+12%) ---
            elif (max_h > avg_h * 1.12 or max_a > avg_a * 1.12) and not is_already_sent(m_id, "value"):
                target = home if max_h > avg_h * 1.12 else away
                v_k = max_h if max_h > avg_h * 1.12 else max_a
                v_avg = avg_h if max_h > avg_h * 1.12 else avg_a
                v_msg = f"💎 *VALUE BET* 💎\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n✅ TYP: *{target.upper()}*\n\n📈 Kurs: `{v_k:.2f}`\n📊 Średnia: `{v_avg:.2f}`\n━━━━━━━━━━━━━━━"
                send_msg(v_msg)
                mark_as_sent(m_id, "value")

            # --- 4. PEWNIAKI ---
            min_avg = min(avg_h, avg_a)
            if min_avg <= 1.70 and not is_already_sent(m_id, "daily"):
                tag = "🔥 *PEWNIAK*" if min_avg <= 1.30 else "⭐ *WARTE UWAGI*"
                pick = f"✅ TYP: *{home.upper()}*" if avg_h < avg_a else f"✅ TYP: *{away.upper()}*"
                msg = f"{tag}\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n{pick}\n🟢 Kurs średni: `{min_avg:.2f}`\n━━━━━━━━━━━━━━━\n⏰ `{m_dt.strftime('%d.%m %H:%M')}`"
                send_msg(msg)
                mark_as_sent(m_id, "daily")

        time.sleep(1)

if __name__ == "__main__":
    run_pro_radar()
