import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

# Filtry kuponu
MIN_SINGLE_ODD = 1.25
MAX_SINGLE_ODD = 1.60
STAKE = 100.0  # Twoja stawka
TAX_RATE = 0.88

# Progi dla "Złotej Okazji"
GOLDEN_MAX_ODD = 1.35  # Tylko najsilniejsi faworyci

SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga",
    "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_france_ligue_one": "🇫🇷 Ligue 1",
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "soccer_uefa_champions_league": "🇪🇺 Liga Mistrzów",
    "basketball_nba": "🏀 NBA",
}

STATE_FILE = "sent.json"

def load_data():
    if not os.path.exists(STATE_FILE): return []
    try:
        with open(STATE_FILE, "r") as f: return json.load(f)
    except: return []

def save_data(data):
    with open(STATE_FILE, "w") as f: json.dump(data[-500:], f)

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"})

def run():
    now = datetime.now(timezone.utc)
    sent_ids = load_data()
    all_favorites = []

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                               params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code == 200:
                    matches = r.json()
                    break
            except: continue

        if not matches: continue

        for m in matches:
            m_id = m["id"]
            if m_id in sent_ids: continue
            
            m_dt = datetime.fromisoformat(m["commence_time"].replace('Z', '+00:00'))
            if m_dt < now or m_dt > (now + timedelta(hours=48)): continue

            home, away = m["home_team"], m["away_team"]
            h_odds, a_odds = [], []

            for bm in m.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        for o in market["outcomes"]:
                            if o["name"] == home: h_odds.append(o["price"])
                            if o["name"] == away: a_odds.append(o["price"])

            if len(h_odds) < 5: continue # Minimum 5 bukmacherów dla wiarygodności
            avg_h, avg_a = sum(h_odds)/len(h_odds), sum(a_odds)/len(a_odds)

            # Klasyfikacja typu
            is_golden = False
            picked_team = None
            odds_value = 0

            if MIN_SINGLE_ODD <= avg_h <= MAX_SINGLE_ODD:
                picked_team, odds_value = home, avg_h
                vs_team = away
                if avg_h <= GOLDEN_MAX_ODD: is_golden = True
            elif MIN_SINGLE_ODD <= avg_a <= MAX_SINGLE_ODD:
                picked_team, odds_value = away, avg_a
                vs_team = home
                if avg_a <= GOLDEN_MAX_ODD: is_golden = True

            if picked_team:
                all_favorites.append({
                    "id": m_id, "team": picked_team, "odd": odds_value, 
                    "league": sport_label, "vs": vs_team, "golden": is_golden
                })

    # Tworzenie Double (AKO2)
    if len(all_favorites) >= 2:
        # Najpierw szukamy par GOLDEN + GOLDEN
        goldens = [f for f in all_favorites if f['golden']]
        standards = [f for f in all_favorites if not f['golden']]
        
        # Łączymy w pary (najpierw złote, potem reszta)
        final_list = goldens + standards
        
        for i in range(0, len(final_list) - 1, 2):
            p1, p2 = final_list[i], final_list[i+1]
            
            # Jeśli oba mecze są złote, dajemy specjalny nagłówek
            is_super_double = p1['golden'] and p2['golden']
            header = "🌟 **ZŁOTY DOUBLE (HIGH PROBABILITY)** 🌟" if is_super_double else "🚀 **KUPON DOUBLE (AKO)**"
            
            ako = round(p1['odd'] * p2['odd'], 2)
            win = round((STAKE * TAX_RATE * ako) - STAKE, 2)

            msg = (
                f"{header}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"1️⃣ {p1['league']} {'⭐' if p1['golden'] else ''}\n"
                f"🏟 **{p1['team']}** vs {p1['vs']}\n"
                f"🎯 Kurs: `{p1['odd']:.2f}`\n\n"
                f"2️⃣ {p2['league']} {'⭐' if p2['golden'] else ''}\n"
                f"🏟 **{p2['team']}** vs {p2['vs']}\n"
                f"🎯 Kurs: `{p2['odd']:.2f}`\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📊 Kurs łączny: `{ako}`\n"
                f"💰 Stawka: `{STAKE} PLN`\n"
                f"💵 **ZYSK NETTO: {win} PLN**"
            )
            
            send_msg(msg)
            sent_ids.extend([p1['id'], p2['id']])
    
    save_data(sent_ids)

if __name__ == "__main__":
    run()
