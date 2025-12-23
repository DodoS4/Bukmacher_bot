import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA KLUCZY (Z SEKCJI SECRETS) ---
F_KEY = os.getenv('F_KEY')
T_TOKEN = os.getenv('T_TOKEN')
T_CHAT = os.getenv('T_CHAT')
GEMINI_KEY = os.getenv('GEMINI_KEY')

LEAGUES = ['PL', 'BL1', 'PD', 'SA', 'FL1', 'CL', 'PPL', 'DED', 'ELC']

def send_msg(txt):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {'chat_id': T_CHAT, 'text': txt, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def ask_gemini_supreme(prompt_text):
    if not GEMINI_KEY:
        return "Analiza statystyczna sugeruje przewagę."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    # Rozbudowany prompt, by AI było bardziej konkretne
    payload = {
        "contents": [{
            "parts": [{"text": f"Jesteś profesjonalnym typerem. Analizuj mecz: {prompt_text}. "
                               f"Podaj: 1. Typ (np. 1, 1X, BTTS lub Over 2.5), 2. Krótkie uzasadnienie, "
                               f"3. Przewidywany wynik. Max 50 słów."}]
        }]
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "AI zajęte. Statystyki wskazują na ciekawą okazję."

def get_general_stats(team_id, headers):
    try:
        time.sleep(1.2) # Ochrona limitu API
        url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED&limit=5"
        res = requests.get(url, headers=headers, timeout=10).json()
        pts, gs, gc = 0, 0, 0
        for m in res.get('matches', []):
            is_h = m['homeTeam']['id'] == team_id
            win = m['score']['winner']
            if (win == 'HOME_TEAM' and is_h) or (win == 'AWAY_TEAM' and not is_h): pts += 3
            elif win == 'DRAW': pts += 1
            gs += m['score']['fullTime']['home'] if is_h else m['score']['fullTime']['away']
            gc += m['score']['fullTime']['away'] if is_h else m['score']['fullTime']['home']
        return pts, gs, gc
    except: return 0, 0, 0

def run_supreme_analysis():
    headers = {'X-Auth-Token': f"{F_KEY}"}
    now = datetime.now(timezone.utc)
    found_matches = False

    for lg in LEAGUES:
        try:
            url = f"https://api.football-data.org/v4/competitions/{lg}/matches?status=SCHEDULED"
            res = requests.get(url, headers=headers).json()
            
            for m in res.get('matches', []):
                m_dt = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                
                # RADAR: Szukamy meczów zaczynających się w ciągu najbliższych 12 godzin
                if now < m_dt < now + timedelta(hours=12):
                    h_t, a_t = m['homeTeam'], m['awayTeam']
                    h_pts, h_gs, h_gc = get_general_stats(h_t['id'], headers)
                    a_pts, a_gs, a_gc = get_general_stats(a_t['id'], headers)
                    
                    # POLUZOWANE KRYTERIA (Więcej typów):
                    # Jeśli jedna drużyna jest wyraźnie lepsza LUB pada dużo bramek
                    if abs(h_pts - a_pts) >= 3 or (h_gs + a_gs) >= 8:
                        found_matches = True
                        context = f"{h_t['name']} vs {a_t['name']}. Formy: {h_pts}pkt vs {a_pts}pkt. Bramki: {h_gs} vs {a_gs}."
                        analiza = ask_gemini_supreme(context)
                        
                        msg = (f"🔥 *OKAZJA - RADAR 12H* | {lg}\n"
                               f"🏠 *{h_t['name']}* vs {a_t['name']}\n"
                               f"📊 Formy: `{h_pts}pkt` vs `{a_pts}pkt` | Gole: `{h_gs}:{h_gc}`\n"
                               f"🧠 *AI:* _{analiza.strip()}_\n"
                               f"⏰ Start: `{m_dt.strftime('%H:%M')}`")
                        send_msg(msg)
                        time.sleep(2)
        except: continue
    
    if not found_matches:
        print("Brak meczów spełniających kryteria w najbliższym oknie 12h.")

if __name__ == "__main__":
    # Raport startowy co 2h
    now_pl = datetime.now(timezone.utc) + timedelta(hours=1)
    print(f"Uruchomiono skanowanie: {now_pl.strftime('%H:%M')}")
    
    run_supreme_analysis()
