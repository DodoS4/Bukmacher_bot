import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA KLUCZY ---
F_KEY = os.getenv('F_KEY')
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
GEMINI_KEY = os.getenv('GEMINI_KEY')
ODDS_KEY = os.getenv('ODDS_KEY') # Dodaj to w GitHub Secrets!

LEAGUES = ['PL', 'BL1', 'PD', 'SA', 'FL1', 'CL', 'PPL', 'DED', 'ELC']
DB_FILE = "sent_matches.txt"

def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def get_odds(home_team, away_team):
    if not ODDS_KEY: return "Brak danych o kursach"
    try:
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
        res = requests.get(url).json()
        for match in res:
            if home_team in match['home_team'] or match['home_team'] in home_team:
                odds = match['bookmakers'][0]['markets'][0]['outcomes']
                o_h = next(o['price'] for o in odds if o['name'] == match['home_team'])
                o_a = next(o['price'] for o in odds if o['name'] == match['away_team'])
                return f"Kursy: 1:{o_h} | 2:{o_a}"
    except: pass
    return "Kursy niedostępne"

def ask_gemini_pro(data_ctx):
    if not GEMINI_KEY: return "Analiza niedostępna."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    prompt = (f"Jesteś ekspertem bukmacherskim. Przeanalizuj dane: {data_ctx}. "
              "Podaj: 1. Propozycję typu (1, X2, BTTS lub Over 2.5), 2. Wynik, "
              "3. Confidence Level (1-10/10) z emoji. Max 60 słów.")
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except: return "Błąd analizy AI."

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
        time.sleep(1.2)
        url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED&limit=5"
        res = requests.get(url, headers=headers).json()
        pts = sum(3 if (m['score']['winner'] == 'HOME_TEAM' and m['homeTeam']['id'] == team_id) or 
                    (m['score']['winner'] == 'AWAY_TEAM' and m['awayTeam']['id'] == team_id) else 1 
                    if m['score']['winner'] == 'DRAW' else 0 for m in res.get('matches', []))
        goals = sum(m['score']['fullTime']['home'] if m['homeTeam']['id'] == team_id else m['score']['fullTime']['away'] for m in res.get('matches', []))
        return pts, goals
    except: return 0, 0

def run_radar():
    headers = {'X-Auth-Token': f"{F_KEY}"}
    now = datetime.now(timezone.utc)
    for lg in LEAGUES:
        try:
            url = f"https://api.football-data.org/v4/competitions/{lg}/matches?status=SCHEDULED"
            res = requests.get(url, headers=headers).json()
            for m in res.get('matches', []):
                m_id = m['id']
                m_dt = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                
                if now < m_dt < now + timedelta(hours=12) and not is_already_sent(m_id):
                    h_t, a_t = m['homeTeam'], m['awayTeam']
                    h_p, h_g = get_stats(h_t['id'])
                    a_p, a_g = get_stats(a_t['id'])
                    kursy = get_odds(h_t['name'], a_t['name'])
                    
                    if h_p >= 5 or (h_g + a_g) >= 7:
                        ctx = f"{h_t['name']} vs {a_t['name']}. Pkt: {h_p}-{a_p}. Gole: {h_g}-{a_g}. {kursy}"
                        analiza = ask_gemini_pro(ctx)
                        
                        msg = (f"🎯 *TYP DNIA* | {lg}\n"
                               f"🏠 *{h_t['name']}* - {a_t['name']}\n"
                               f"📊 {kursy}\n"
                               f"🧠 *AI:* _{analiza.strip()}_\n"
                               f"⏰ Start: `{m_dt.strftime('%H:%M')}`")
                        send_msg(msg)
                        mark_as_sent(m_id)
                        time.sleep(2)
        except: continue

if __name__ == "__main__":
    run_radar()
