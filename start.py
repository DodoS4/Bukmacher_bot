import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
KEYS_POOL = [os.getenv(f"ODDS_KEY{i}") for i in ["", "_2", "_3", "_4", "_5"]]
API_KEYS = [k for k in KEYS_POOL if k]

STAKE_STANDARD = 50.0
STAKE_GOLDEN = 100.0
TAX_RATE = 0.88

MIN_SINGLE_ODD = 1.25
MAX_SINGLE_ODD = 1.60
GOLDEN_MAX_ODD = 1.35
MAX_VARIANCE = 0.08 
MIN_BOOKMAKERS = 7  # OPCJA 4: Minimum 7 bukmacherów dla wiarygodności danych

SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League",
    "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga",
    "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_france_ligue_one": "🇫🇷 Ligue 1",
    "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "soccer_netherlands_ere_divisie": "🇳🇱 Eredivisie",
    "soccer_portugal_primeira_liga": "🇵🇹 Primeira Liga",
    "soccer_turkey_super_lig": "🇹🇷 Super Lig",
    "soccer_belgium_first_div": "🇧🇪 Jupiler Pro League",
    "soccer_uefa_champions_league": "🇪🇺 Liga Mistrzów",
    "soccer_uefa_europa_league": "🇪🇺 Liga Europy",
    "soccer_uefa_europa_conference_league": "🇪🇺 Liga Konferencji",
    "basketball_nba": "🏀 NBA",
}

STATE_FILE = "sent.json"

def load_data():
    if not os.path.exists(STATE_FILE): return []
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except: return []

def save_data(data):
    with open(STATE_FILE, "w") as f:
        json.dump(data[-500:], f)

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(f"Błąd wysyłki Telegram: {e}")

def run():
    now = datetime.now(timezone.utc)
    sent_ids = load_data()
    
    # OPCJA 3: Grupowanie meczów według lig
    leagues_pools = {} 

    print(f"Rozpoczynam skanowanie: {now.strftime('%Y-%m-%d %H:%M')}")

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches = None
        for key in API_KEYS:
            try:
                r = requests.get(
                    f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                    params={"apiKey": key, "regions": "eu", "markets": "h2h"},
                    timeout=15
                )
                if r.status_code == 200:
                    matches = r.json()
                    break
                elif r.status_code == 429:
                    continue # Spróbuj kolejny klucz
            except: continue

        if not matches: continue

        for m in matches:
            m_id = m["id"]
            if m_id in sent_ids: continue
            
            # OPCJA 4: Filtr liczby bukmacherów (płynność rynku)
            if len(m.get("bookmakers", [])) < MIN_BOOKMAKERS:
                continue

            m_dt_utc = datetime.fromisoformat(m["commence_time"].replace('Z', '+00:00'))
            m_dt_pl = m_dt_utc + timedelta(hours=1) # Czas zimowy (dla letniego +2h)
            
            if m_dt_utc < now or m_dt_utc > (now + timedelta(hours=48)): continue

            home, away = m["home_team"], m["away_team"]
            h_odds, a_odds = [], []

            for bm in m.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        for o in market["outcomes"]:
                            if o["name"] == home: h_odds.append(o["price"])
                            if o["name"] == away: a_odds.append(o["price"])

            if len(h_odds) < MIN_BOOKMAKERS: continue
                
            avg_h, min_h, max_h = sum(h_odds)/len(h_odds), min(h_odds), max(h_odds)
            avg_a, min_a, max_a = sum(a_odds)/len(a_odds), min(a_odds), max(a_odds)

            var_h = (max_h - min_h) / avg_h
            var_a = (max_a - min_a) / avg_a

            pick = None
            # Logika wyboru faworyta
            if MIN_SINGLE_ODD <= avg_h <= MAX_SINGLE_ODD and var_h <= MAX_VARIANCE:
                pick = {"id": m_id, "team": home, "odd": avg_h, "league": sport_label, "vs": away, 
                        "golden": avg_h <= GOLDEN_MAX_ODD, "dropping": (avg_h - min_h) > 0.05, 
                        "date": m_dt_pl.strftime("%d.%m %H:%M")}
            elif MIN_SINGLE_ODD <= avg_a <= MAX_SINGLE_ODD and var_a <= MAX_VARIANCE:
                pick = {"id": m_id, "team": away, "odd": avg_a, "league": sport_label, "vs": home, 
                        "golden": avg_a <= GOLDEN_MAX_ODD, "dropping": (avg_a - min_a) > 0.05, 
                        "date": m_dt_pl.strftime("%d.%m %H:%M")}

            if pick:
                if sport_label not in leagues_pools:
                    leagues_pools[sport_label] = []
                leagues_pools[sport_label].append(pick)

    # --- OPCJA 3: INTELIGENTNE PAROWANIE MIĘDZY LIGAMI ---
    all_picks = []
    for league_name in leagues_pools:
        # Sortujemy wewnątrz ligi (najlepsze na początek)
        leagues_pools[league_name].sort(key=lambda x: (x['golden'], x['dropping']), reverse=True)
        all_picks.extend(leagues_pools[league_name])

    # Globalne sortowanie: najpierw "Złote" typy
    all_picks.sort(key=lambda x: (x['golden'], x['dropping']), reverse=True)

    while len(all_picks) >= 2:
        p1 = all_picks.pop(0) # Najlepszy dostępny typ
        
        # Szukamy partnera z INNEJ ligi (dywersyfikacja)
        p2_index = -1
        for i in range(len(all_picks)):
            if all_picks[i]['league'] != p1['league']:
                p2_index = i
                break
        
        if p2_index != -1:
            p2 = all_picks.pop(p2_index)
            
            # Parametry kuponu
            is_super = p1['golden'] and p2['golden']
            current_stake = STAKE_GOLDEN if is_super else STAKE_STANDARD
            ako = round(p1['odd'] * p2['odd'], 2)
            total_return = round(current_stake * TAX_RATE * ako, 2)
            profit = round(total_return - current_stake, 2)
            
            drop_tag = " 🔥 SPADEK" if (p1['dropping'] or p2['dropping']) else ""
            header = f"🌟 **ZŁOTY DOUBLE**{drop_tag}" if is_super else f"🚀 **KUPON DOUBLE**{drop_tag}"

            msg = (
                f"{header}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"1️⃣ {p1['league']} {'⭐' if p1['golden'] else ''}\n"
                f"🏟 **{p1['team']}** vs {p1['vs']}\n"
                f"📅 Start: `{p1['date']}`\n"
                f"📈 Kurs: `{p1['odd']:.2f}`\n\n"
                f"2️⃣ {p2['league']} {'⭐' if p2['golden'] else ''}\n"
                f"🏟 **{p2['team']}** vs {p2['vs']}\n"
                f"📅 Start: `{p2['date']}`\n"
                f"📈 Kurs: `{p2['odd']:.2f}`\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📊 AKO: `{ako:.2f}` | 💵 Stawka: `{current_stake} PLN`\n"
                f"💰 **ZYSK NETTO: {profit} PLN**\n"
                f"📊 Pewność (7+ bukm.): `Wysoka`"
            )
            
            send_msg(msg)
            sent_ids.extend([p1['id'], p2['id']])
        else:
            # Nie znaleziono meczu z innej ligi do pary
            break
    
    save_data(sent_ids)
    print("Skanowanie zakończone.")

if __name__ == "__main__":
    run()
