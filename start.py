import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
ODDS_KEY = os.getenv('ODDS_KEY')

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
        open(DB_FILE, 'w').close()
        return False
    with open(DB_FILE, "r") as f:
        return unique_key in f.read().splitlines()

def mark_as_sent(match_id, category=""):
    with open(DB_FILE, "a") as f:
        f.write(f"{match_id}_{category}\n")

def run_pro_radar():
    if not ODDS_KEY: return
    now = datetime.now(timezone.utc)
    # LIMIT 3 DNI (72 godziny)
    limit_date = now + timedelta(days=3)
    
    # STATUS SYSTEMU
    if now.hour == 0 or os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch':
        status_msg = "🟢 *STATUS SYSTEMU: AKTYWNY*\n✅ Data: `" + now.strftime('%d.%m.%Y') + "`\n🤖 Skanowanie ofert (max 3 dni naprzód)..."
        send_msg(status_msg)

    for sport_key, sport_label in SPORTS_CONFIG.items():
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
            response = requests.get(url, timeout=10)
            if response.status_code != 200: continue
            res = response.json()

            for match in res:
                m_id = match['id']
                home = match['home_team']
                away = match['away_team']
                m_dt = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

                # --- FILTR 3 DNI ---
                if m_dt > limit_date:
                    continue

                all_h, all_a = [], []
                for bm in match['bookmakers']:
                    for market in bm['markets']:
                        if market['key'] == 'h2h':
                            try:
                                h_o = next(o['price'] for o in market['outcomes'] if o['name'] == home)
                                a_o = next(o['price'] for o in market['outcomes'] if o['name'] == away)
                                all_h.append(h_o)
                                all_a.append(a_o)
                            except: continue

                if not all_h: continue
                avg_h, avg_a = sum(all_h)/len(all_h), sum(all_a)/len(all_a)
                max_h, max_a = max(all_h), max(all_a)

                # 1. VALUE BET (BUKMACHER ZASPAŁ)
                if (max_h > avg_h * 1.12 or max_a > avg_a * 1.12) and not is_already_sent(m_id, "value"):
                    target = home if max_h > avg_h * 1.12 else away
                    val_k = max_h if max_h > avg_h * 1.12 else max_a
                    avg_k = avg_h if max_h > avg_h * 1.12 else avg_a
                    v_msg = f"💎 *BUKMACHER ZASPAŁ!* 💎\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n✅ STAWIAJ NA: *{target.upper()}*\n\n📈 Kurs OKAZJA: `{val_k:.2f}`\n📊 Średnia: `{avg_k:.2f}`\n━━━━━━━━━━━━━━━"
                    send_msg(v_msg)
                    mark_as_sent(m_id, "value")

                # 2. PEWNIAKI
                min_avg = min(avg_h, avg_a)
                if min_avg <= 1.75 and not is_already_sent(m_id, "daily"):
                    tag = "🔥 *PEWNIAK*" if min_avg <= 1.35 else "⭐ *WARTE UWAGI*"
                    if avg_h < avg_a:
                        pick = f"✅ STAWIAJ NA: *{home.upper()}*\n\n🟢 {home}: `{avg_h:.2f}`\n⚪ {away}: `{avg_a:.2f}`"
                    else:
                        pick = f"✅ STAWIAJ NA: *{away.upper()}*\n\n⚪ {home}: `{avg_h:.2f}`\n🟢 {away}: `{avg_a:.2f}`"
                    
                    sugestia = "\n🛡️ _Sugerowana podpórka (1X/X2)_" if "⚽" in sport_label and min_avg > 1.40 else ""
                    msg = f"{tag}\n🏆 {sport_label}\n━━━━━━━━━━━━━━━\n{pick}\n━━━━━━━━━━━━━━━\n⏰ `{m_dt.strftime('%d.%m %H:%M')}` UTC{sugestia}"
                    send_msg(msg)
                    mark_as_sent(m_id, "daily")
            time.sleep(1)
        except:
            continue

if __name__ == "__main__":
    run_pro_radar()
