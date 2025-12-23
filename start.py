import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA KLUCZY (GITHUB SECRETS) ---
F_KEY = os.getenv('F_KEY')
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
GEMINI_KEY = os.getenv('GEMINI_KEY')
ODDS_KEY = os.getenv('ODDS_KEY')

# Wszystkie darmowe ligi z football-data.org
LEAGUES = ['PL', 'ELC', 'BL1', 'SA', 'PD', 'FL1', 'DED', 'PPL', 'BSA', 'CL', 'EC', 'WC']
DB_FILE = "sent_matches.txt"

def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Błąd wysyłki Telegram: {e}")

def get_odds(home_team, away_team):
    """Pobiera kursy z The Odds API"""
    if not ODDS_KEY: return "Kursy: brak klucza"
    try:
        # Szukamy kursów dla piłki nożnej w Europie
        url = f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={ODDS_KEY}&regions=eu&markets=h2h"
        res = requests.get(url, timeout=10).json()
        for match in res:
            # Dopasowanie nazwy drużyny (uproszczone)
            if home_team in match['home_team'] or match['home_team'] in home_team:
                odds = match['bookmakers'][0]['markets'][0]['outcomes']
                o_h = next((o['price'] for o in odds if o['name'] == match['home_team']), "?")
                o_a = next((o['price'] for o in odds if o['name'] == match['away_team']), "?")
                o_d = next((o['price'] for o in odds if o['name'] == "Draw"), "?")
                return f"Kursy: 1:{o_h} | X:{o_d} | 2:{o_a}"
    except: pass
    return "Kursy: niedostępne dla tego meczu"

def ask_gemini_pro(data_ctx):
    """Analiza ekspercka AI Gemini"""
    if not GEMINI_KEY: return "Analiza AI niedostępna."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    
    prompt = (f"Jesteś profesjonalnym analitykiem sportowym. Przeanalizuj mecz na podstawie danych: {data_ctx}. "
              "Zaproponuj: 1. Konkretny typ (np. Wygrana gospodarzy, BTTS, lub Over 2.5), "
              "2. Przewidywany wynik, 3. Confidence Level (1-10/10) używając emoji. "
              "Bądź konkretny, max 50 słów.")
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=15)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "AI nie mogło wygenerować analizy. Sprawdź statystyki ręcznie."

def is_already_sent(match_id):
    """Sprawdza czy mecz był już wysłany (pamięć bota)"""
    if not os.path.exists(DB_FILE): return False
    with open(DB_FILE, "r") as f:
        return str(match_id) in f.read().splitlines()

def mark_as_sent(match_id):
    """Zapisuje ID meczu do bazy"""
    with open(DB_FILE, "a") as f:
        f.write(str(match_id) + "\n")

def get_stats(team_id):
    """Pobiera formę drużyny (ostatnie 5 meczów)"""
    headers = {'X-Auth-Token': f"{F_KEY}"}
    try:
        time.sleep(1.5) # Ważne: ochrona limitu 10 zapytań/min
        url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED&limit=5"
        res = requests.get(url, headers=headers, timeout=10).json()
        
        pts, goals = 0, 0
        matches = res.get('matches', [])
        for m in matches:
            is_h = m['homeTeam']['id'] == team_id
            win = m['score']['winner']
            if (win == 'HOME_TEAM' and is_h) or (win == 'AWAY_TEAM' and not is_h):
                pts += 3
            elif win == 'DRAW':
                pts += 1
            goals += m['score']['fullTime']['home'] if is_h else m['score']['fullTime']['away']
        return pts, goals
    except:
        return 0, 0

def run_radar():
    """Główna funkcja skanująca"""
    headers = {'X-Auth-Token': f"{F_KEY}"}
    now = datetime.now(timezone.utc)
    # Zwiększamy zasięg do 48h, aby widzieć nadchodzące mecze w święta
    future_window = now + timedelta(hours=48) 
    
    print(f"--- Start skanowania: {now.strftime('%Y-%m-%d %H:%M')} ---")
    
    for lg in LEAGUES:
        try:
            print(f"Sprawdzam ligę: {lg}...")
            url = f"https://api.football-data.org/v4/competitions/{lg}/matches?status=SCHEDULED"
            res = requests.get(url, headers=headers, timeout=10).json()
            
            for m in res.get('matches', []):
                m_id = m['id']
                m_dt = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                
                if now < m_dt < future_window and not is_already_sent(m_id):
                    h_t, a_t = m['homeTeam'], m['awayTeam']
                    
                    # Pobieramy statystyki formy
                    h_p, h_g = get_stats(h_t['id'])
                    a_p, a_g = get_stats(a_t['id'])
                    
                    # Pobieramy kursy
                    kursy = get_odds(h_t['name'], a_t['name'])
                    
                    # WARUNEK WYSYŁKI: dowolny mecz (żebyś widział że działa)
                    # Możesz to zmienić na: if h_p >= 7 or abs(h_p - a_p) >= 4:
                    if h_p >= 0: 
                        ctx = f"{h_t['name']} vs {a_t['name']}. Formy(5m): {h_p}pkt-{a_p}pkt. Gole strzelone: {h_g}-{a_g}. {kursy}"
                        analiza = ask_gemini_pro(ctx)
                        
                        msg = (f"⚽ *PROPOZYCJA TYPU* | {lg}\n"
                               f"🏠 *{h_t['name']}* - {a_t['name']}\n"
                               f"📊 {kursy}\n"
                               f"📝 *Staty (5m):* `{h_p}pkt` vs `{a_p}pkt` | Gole: `{h_g}` vs `{a_g}`\n\n"
                               f"🧠 *Analiza AI:* _{analiza.strip()}_\n"
                               f"⏰ Start: `{m_dt.strftime('%d.%m %H:%M')}` UTC")
                        
                        send_msg(msg)
                        mark_as_sent(m_id)
                        print(f"Wysłano typ: {h_t['name']} vs {a_t['name']}")
                        time.sleep(2) # Anty-spam Telegram
            
            time.sleep(2) # Przerwa między ligami (limit API)
        except Exception as e:
            print(f"Błąd w lidze {lg}: {e}")
            continue

if __name__ == "__main__":
    run_radar()
