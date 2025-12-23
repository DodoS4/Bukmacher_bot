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
    'icehockey_nhl': '🏒 NHL'
}

DB_FILE = "sent_matches.txt"
MIN_ODDS = 1.40  # Twój nowy minimalny kurs

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
        with open(DB_FILE, 'w') as f: pass
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
        send_msg("🚀 *Radar uruchomiony ręcznie...* Filtruję kursy od 1.40!")

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
            margin = (1/max_h) + (1/max_a) + (1/max_d if max_d else 0)
            if margin < 0.985 and not is_already_sent(m_id, "surebet"):
                # Surebety wysyłamy bez względu na kurs, bo to darmowy zysk, 
                # ale jeśli chcesz filtrować też tutaj, daj znać.
                profit = (1 - margin) * 100
                s_msg = f"🚀 *SUPER OKAZJA: SUREBET!* 🚀\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n💰 Zysk: `+{profit:.2f}%` (pewny zysk)\n\n🏠 1: `{max_h:.2f}`\n✈️ 2: `{max_a:.2f}`"
                if max_d: s_msg += f"\n🤝 X: `{max_d:.2f}`"
                send_msg(s_msg)
                mark_as_sent(m_id, "surebet")

            # --- 2. MEGA VALUE (ZASPAŁ +25%) + FILTR 1.40 ---
            elif (max_h > avg_h * 1.25 or max_a > avg_a * 1.25):
                target_odds = max_h if max_h > avg_h * 1.25 else max_a
                if target_odds >= MIN_ODDS and not is_already_sent(m_id, "mega"):
                    target = home if max_h > avg_h * 1.25 else away
                    m_msg = f"🔥 *BUKMACHER ZASPAŁ! (MEGA)* 🔥\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n✅ POTĘŻNA OKAZJA: *{target.upper()}*\n\n📈 Kurs: `{target_odds:.2f}`\n📊 Średnia: `{avg_h if target==home else avg_a:.2f}`\n━━━━━━━━━━━━━━━"
                    send_msg(m_msg)
                    mark_as_sent(m_id, "mega")

            # --- 3. VALUE BET (ZASPAŁ +12%) + FILTR 1.40 ---
            elif (max_h > avg_h * 1.12 or max_a > avg_a * 1.12):
                target_odds = max_h if max_h > avg_h * 1.12 else max_a
                if target_odds >= MIN_ODDS and not is_already_sent(m_id, "value"):
                    target = home if max_h > avg_h * 1.12 else away
                    v_msg = f"💎 *BUKMACHER ZASPAŁ!* 💎\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n✅ TYP: *{target.upper()}*\n\n📈 Kurs: `{target_odds:.2f}`\n📊 Średnia: `{avg_h if target==home else avg_a:.2f}`\n━━━━━━━━━━━━━━━"
                    send_msg(v_msg)
                    mark_as_sent(m_id, "value")

            # --- 4. PEWNIAKI + FILTR 1.40 ---
            min_avg = min(avg_h, avg_a)
            if MIN_ODDS <= min_avg <= 1.70 and not is_already_sent(m_id, "daily"):
                pick = f"*{home.upper()}*" if avg_h < avg_a else f"*{away.upper()}*"
                msg = f"⭐ *WARTE UWAGI*\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n✅ STAWIAJ NA: {pick}\n🟢 Kurs średni: `{min_avg:.2f}`\n━━━━━━━━━━━━━━━"
                send_msg(msg)
                mark_as_sent(m_id, "daily")

        time.sleep(1)

if __name__ == "__main__":
    run_pro_radar()
