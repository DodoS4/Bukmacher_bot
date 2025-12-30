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
    except: pass

def run():
    now = datetime.now(timezone.utc)
    sent_ids = load_data()
    all_favorites = []

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
            except: continue

        if not matches: continue

        for m in matches:
            m_id = m["id"]
            if m_id in sent_ids: continue
            
            # Przeliczenie na czas polski (UTC + 1 lub +2 zależnie od pory roku)
            # Dla uproszczenia dodajemy 1h (zima) lub 2h (lato) lub korzystamy z timedelta
            m_dt_utc = datetime.fromisoformat(m["commence_time"].replace('Z', '+00:00'))
            m_dt_pl = m_dt_utc + timedelta(hours=1) # Czas zimowy (dla lata zmień na 2)
            
            if m_dt_utc < now or m_dt_utc > (now + timedelta(hours=48)): continue

            home, away = m["home_team"], m["away_team"]
            h_odds, a_odds = [], []

            for bm in m.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        for o in market["outcomes"]:
                            if o["name"] == home: h_odds.append(o["price"])
                            if o["name"] == away: a_odds.append(o["price"])

            if len(h_odds) < 4: continue
                
            avg_h, min_h, max_h = sum(h_odds)/len(h_odds), min(h_odds), max(h_odds)
            avg_a, min_a, max_a = sum(a_odds)/len(a_odds), min(a_odds), max(a_odds)

            var_h = (max_h - min_h) / avg_h
            var_a = (max_a - min_a) / avg_a

            pick = None
            date_str = m_dt_pl.strftime("%d.%m %H:%M")

            if MIN_SINGLE_ODD <= avg_h <= MAX_SINGLE_ODD and var_h <= MAX_VARIANCE:
                is_dropping = (avg_h - min_h) > 0.05
                pick = {"id": m_id, "team": home, "odd": avg_h, "league": sport_label, "vs": away, "golden": avg_h <= GOLDEN_MAX_ODD, "dropping": is_dropping, "date": date_str}
            elif MIN_SINGLE_ODD <= avg_a <= MAX_SINGLE_ODD and var_a <= MAX_VARIANCE:
                is_dropping = (avg_a - min_a) > 0.05
                pick = {"id": m_id, "team": away, "odd": avg_a, "league": sport_label, "vs": home, "golden": avg_a <= GOLDEN_MAX_ODD, "dropping": is_dropping, "date": date_str}

            if pick: all_favorites.append(pick)

    if len(all_favorites) >= 2:
        all_favorites.sort(key=lambda x: (x['golden'], x['dropping']), reverse=True)
        
        for i in range(0, len(all_favorites) - 1, 2):
            p1, p2 = all_favorites[i], all_favorites[i+1]
            is_super = p1['golden'] and p2['golden']
            current_stake = STAKE_GOLDEN if is_super else STAKE_STANDARD
            
            drop_tag = " 🔥 SPADEK" if (p1['dropping'] or p2['dropping']) else ""
            header = f"🌟 **ZŁOTY DOUBLE**{drop_tag}" if is_super else f"🚀 **KUPON DOUBLE**{drop_tag}"
            
            ako = round(p1['odd'] * p2['odd'], 2)
            total_return = round(current_stake * TAX_RATE * ako, 2)
            profit = round(total_return - current_stake, 2)

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
                f"📊 Pewność rynku: `Wysoka`"
            )
            send_msg(msg)
            sent_ids.extend([p1['id'], p2['id']])
    
    save_data(sent_ids)

if __name__ == "__main__":
    run()
