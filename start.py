import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA KLUCZY (POBIERANE Z GITHUB SECRETS) ---
F_KEY = os.getenv('F_KEY')
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
GEMINI_KEY = os.getenv('GEMINI_KEY')
ODDS_KEY = os.getenv('ODDS_KEY')

# Lista wszystkich darmowych lig
LEAGUES = ['PL', 'ELC', 'BL1', 'SA', 'PD', 'FL1', 'DED', 'PPL', 'BSA', 'CL', 'EC', 'WC']
DB_FILE = "sent_matches.txt"

def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Błąd Telegram: {e}")

def get_odds(home_team, away_team):
    if not ODDS_KEY: return "Kursy: brak klucza"
    try:
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
        res = requests.get(url, timeout=10).json()
        for match in res:
            if home_team in match['home_team'] or match['home_team'] in home_team:
                odds = match['bookmakers'][0]['markets'][0]['outcomes']
                o_h = next((o['price'] for o in odds if o['name'] == match['home_team']), "?")
                o_a = next((o['price'] for o in odds if o['name'] == match['away_team']), "?")
                o_d = next((o['price'] for o in odds if o['name'] == "Draw"), "?")
                return f"Kursy: 1:{o_h} | X:{o_d} | 2:{o_a}"
    except: pass
    return "Kursy: niedostępne"

def ask_gemini_pro(data_ctx):
    if not GEMINI_KEY: return "Analiza AI niedostępna."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    prompt = (f"Jesteś profesjonalnym analitykiem sportowym. Przeanalizuj mecz: {data_ctx}. "
              "Zaproponuj: 1. Typ (1, X2, BTTS lub Over 2.5), 2. Wynik, "
              "3. Confidence Level (1-10/10) z emoji. Max 50 słów.")
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "AI nie mogło wygenerować analizy."

def is_already_sent(match_id):
    if not os.path.exists(DB_FILE): return False
    with open(DB_FILE, "r") as f:
        return str(match_id) in f.read().splitlines()

def mark_as_sent(match_id):
    with open(DB_FILE, "a") as f:
        f.write(str(match_id) + "\n")

def get_stats(team_id):
    headers = {'X-Auth-Token': f"{F_KEY}"}
    try:
        time.sleep(1.5) # Ochrona limitu API (10 req/min)
        url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED&limit=5"
        res = requests.get(url, headers=headers, timeout=10).json()
        pts, goals = 0, 0
        for m in res.get('matches', []):
            is_h = m['homeTeam']['id'] == team_id
            win = m['score']['winner']
            if (win == 'HOME_TEAM' and is_h) or (win == 'AWAY_TEAM' and not is_h): pts += 3
            elif win == 'DRAW': pts += 1
            goals += m['score']['fullTime']['home'] if is_h else m['score']['fullTime']['away']
        return pts, goals
    except: return 0, 0

def run_radar():
    headers = {'X-Auth-Token': f"{F_KEY}"}
    now = datetime.now(timezone.utc)
    # USTAWIENIE OKNA NA 3 DNI
    future_window = now + timedelta(days=3) 
    
    print(f"--- Start skanowania: {now.strftime('%Y-%m-%d %H:%M')} ---")
    
    for lg in LEAGUES:
        try:
            print(f"Sprawdzam ligę: {lg}...")
            url = f"https://api.football-data.org/v4/competitions/{lg}/matches?status=SCHEDULED"
            res = requests.get(url, headers=headers, timeout=10).json()
            
            for m in res.get('matches', []):
                m_id = m['id']
                m_dt = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                
                # Jeśli mecz jest w ciągu najbliższych 3 dni i nie był wysyłany
                if now < m_dt < future_window and not is_already_sent(m_id):
                    h_t, a_t = m['homeTeam'], m['awayTeam']
                    h_p, h_g = get_stats(h_t['id'])
                    a_p, a_g = get_stats(a_t['id'])
                    kursy = get_odds(h_t['name'], a_t['name'])
                    
                    # Analizuj każdy mecz w oknie (h_p >= 0)
                    ctx = f"{h_t['name']} vs {a_t['name']}. Formy(5m): {h_p}-{a_p} pkt. Gole: {h_g}-{a_g}. {kursy}"
                    analiza = ask_gemini_pro(ctx)
                    
                    msg = (f"🎯 *PROPOZYCJA TYPU (RADAR 3D)* | {lg}\n"
                           f"🏠 *{h_t['name']}* - {a_t['name']}\n"
                           f"📊 {kursy}\n"
                           f"📈 Formy: `{h_p} pkt` vs `{a_p} pkt`\n\n"
                           f"🧠 *AI:* _{analiza.strip()}_\n"
                           f"⏰ Start: `{m_dt.strftime('%d.%m %H:%M')}` UTC")
                    
                    send_msg(msg)
                    mark_as_sent(m_id)
                    print(f"Wysłano: {h_t['name']} vs {a_t['name']}")
                    time.sleep(2) # Anty-spam Telegram
            
            time.sleep(2) # Przerwa między ligami dla API
        except Exception as e:
            print(f"Błąd w lidze {lg}: {e}")
            continue

if __name__ == "__main__":
    run_radar()
