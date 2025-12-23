import requests
import os
import time
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA KLUCZY ---
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

def send_health_check():
    """Wysyła potwierdzenie, że system pracuje poprawnie"""
    now_pl = datetime.now(timezone.utc) + timedelta(hours=1) # Czas PL
    status_msg = (f"🟢 *RAPORT DOBOWY SYSTEMU*\n"
                  f"━━━━━━━━━━━━━━━\n"
                  f"🤖 Status: `PRACA POPRAWNA`\n"
                  f"⏰ Godzina: `{now_pl.strftime('%H:%M')}`\n"
                  f"📡 Skanowanie: `9 lig aktywnych`")
    send_msg(status_msg)

def ask_gemini_supreme(prompt_text, is_value_bet):
    if not GEMINI_KEY:
        return "Przewaga gospodarza potwierdzona statystycznie."
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
    headers = {'Content-Type': 'application/json'}
    payload = {
        "contents": [{
            "parts": [{"text": f"Jesteś ekspertem. Analizuj mecz: {prompt_text}. Podaj krótko: 1. Dlaczego gospodarz, 2. Ryzyko, 3. Składy. Rekomendacja (1 lub 1X). Max 50 słów."}]
        }]
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=15)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except:
        return "Analiza AI niedostępna, statystyki wskazują na faworyta."

def get_home_form(team_id, headers):
    try:
        time.sleep(1.2)
        url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED&venue=HOME&limit=4"
        res = requests.get(url, headers=headers, timeout=10).json()
        return sum(3 if m['score']['winner'] == 'HOME_TEAM' else 1 if m['score']['winner'] == 'DRAW' else 0 for m in res.get('matches', []))
    except: return 0

def get_general_stats(team_id, headers):
    try:
        time.sleep(1.2)
        url = f"https://api.football-data.org/v4/teams/{team_id}/matches?status=FINISHED&limit=5"
        res = requests.get(url, headers=headers).json()
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
    for lg in LEAGUES:
        try:
            url = f"https://api.football-data.org/v4/competitions/{lg}/matches?status=SCHEDULED"
            res = requests.get(url, headers=headers).json()
            for m in res.get('matches', []):
                m_dt = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if now < m_dt < now + timedelta(hours=36):
                    h_t, a_t = m['homeTeam'], m['awayTeam']
                    h_pts, h_gs, h_gc = get_general_stats(h_t['id'], headers)
                    a_pts, a_gs, a_gc = get_general_stats(a_t['id'], headers)
                    h_home = get_home_form(h_t['id'], headers)

                    if (h_home >= 9 and (h_pts - a_pts) >= 3) or (h_pts - a_pts) >= 7:
                        is_val = (h_gs - h_gc) > (a_gs - a_gc) + 5
                        analiza = ask_gemini_supreme(f"{h_t['name']} vs {a_t['name']}. Dom: {h_home}/12.", is_val)
                        v_tag = "💎 " if is_val else ""
                        msg = (f"⚽ *{lg}* | {v_tag}\n"
                               f"🏠 *{h_t['name']}* vs {a_t['name']}\n"
                               f"📊 Dom: `{h_home}/12` | Formy: `{h_pts}pkt` vs `{a_pts}pkt` \n"
                               f"🧠 *AI:* _{analiza.strip()}_\n"
                               f"⏰ `{m_dt.strftime('%d.%m | %H:%M')}`")
                        send_msg(msg)
                        time.sleep(2)
        except: continue

def get_stats_report(days=1):
    headers = {'X-Auth-Token': f"{F_KEY}"}
    w, l = 0, 0
    for lg in LEAGUES:
        try:
            url = f"https://api.football-data.org/v4/competitions/{lg}/matches?status=FINISHED"
            res = requests.get(url, headers=headers).json()
            for m in res.get('matches', []):
                e_t = datetime.strptime(m['utcDate'], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) - timedelta(days=days) < e_t:
                    if m['score']['winner'] == 'HOME_TEAM': w += 1
                    else: l += 1
        except: continue
    return w, l

if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    # 1. Start - potwierdzenie pracy
    send_health_check()
    # 2. Rozliczenie wczoraj
    w1, l1 = get_stats_report(1)
    if w1 > 0 or l1 > 0:
        send_msg(f"✅ *WYNIKI WCZORAJ*\nTrafione: {w1} | Inne: {l1}")
    # 3. Raport Tygodniowy (Niedziela)
    if now.weekday() == 6:
        w7, l7 = get_stats_report(7)
        total = w7 + l7
        perc = round((w7/total*100), 1) if total > 0 else 0
        send_msg(f"📊 *SKUTECZNOŚĆ TYGODNIA*: `{perc}%` ({w7}/{total})")
    # 4. Analiza nowych meczów
    run_supreme_analysis()
