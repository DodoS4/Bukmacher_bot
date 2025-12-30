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
MIN_BOOKMAKERS = 7
MIN_SINGLE_ODD, MAX_SINGLE_ODD = 1.25, 1.60
GOLDEN_MAX_ODD = 1.35
MAX_VARIANCE = 0.08

SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga", "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_france_ligue_one": "🇫🇷 Ligue 1", "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "soccer_uefa_champions_league": "🇪🇺 Liga Mistrzów", "soccer_uefa_europa_league": "🇪🇺 Liga Europy",
    "basketball_nba": "🏀 NBA"
}

COUPONS_FILE = "coupons.json"

# ================= FUNKCJE POMOCNICZE =================

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r") as f: return json.load(f)
    except: return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w") as f: json.dump(coupons[-1000:], f) # Trzymaj ostatnie 1000 kuponów

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

# ================= RAPORTY I WYNIKI =================

def check_results():
    coupons = load_coupons()
    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        
        # Sprawdzamy po 4h od rozpoczęcia ostatniego meczu
        end_time = datetime.fromisoformat(c["end_time"])
        if now > end_time + timedelta(hours=4):
            for key in API_KEYS:
                try:
                    # Pobieranie wyników dla danej dyscypliny
                    r = requests.get(f"https://api.the-odds-api.com/v4/sports/{c['sport_key']}/scores/", 
                                     params={"apiKey": key, "daysFrom": 3}, timeout=15)
                    if r.status_code == 200:
                        scores = r.json()
                        matches_found = 0
                        wins = 0
                        
                        for m_saved in c["matches"]:
                            for s in scores:
                                if s["id"] == m_saved["id"] and s.get("completed"):
                                    matches_found += 1
                                    h_score = s["scores"][0]["score"] if s["scores"] else 0
                                    a_score = s["scores"][1]["score"] if s["scores"] else 0
                                    
                                    # Kto wygrał?
                                    if h_score > a_score: winner = s["home_team"]
                                    elif a_score > h_score: winner = s["away_team"]
                                    else: winner = "Draw"
                                    
                                    if winner == m_saved["picked_team"]: wins += 1
                        
                        if matches_found == len(c["matches"]):
                            c["status"] = "won" if wins == len(c["matches"]) else "lost"
                            updated = True
                            icon = "✅" if c["status"] == "won" else "❌"
                            val = round(c['potential_win'] - c['stake'], 2) if c["status"] == "won" else -c['stake']
                            send_msg(f"{icon} **KUPON ROZLICZONY**\nBilans: `{val:+.2f} PLN`")
                        break
                except: continue
    if updated: save_coupons(coupons)

def send_weekly_report():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    last_week = now - timedelta(days=7)
    
    # Filtrujemy tylko rozliczone kupony z ostatnich 7 dni
    week_coupons = [c for c in coupons if c["status"] != "pending" and 
                    datetime.fromisoformat(c["end_time"]) > last_week]
    
    if not week_coupons: return

    total_stake = sum(c["stake"] for c in week_coupons)
    total_win = sum(c["potential_win"] for c in week_coupons if c["status"] == "won")
    net_profit = total_win - total_stake
    yield_val = (net_profit / total_stake) * 100 if total_stake > 0 else 0
    wins = len([c for c in week_coupons if c["status"] == "won"])
    
    report = (
        f"📅 **PODSUMOWANIE TYGODNIOWE**\n"
        f"━━━━━━━━━━━━━━━\n"
        f" tickets Kupony: `{len(week_coupons)}` (✅ {wins} / ❌ {len(week_coupons)-wins})\n"
        f"💵 Obrót: `{total_stake:.2f} PLN`\n"
        f"💰 Zysk netto: `{net_profit:+.2f} PLN`\n"
        f"📈 Yield: `{yield_val:.2f}%`"
    )
    send_msg(report)

# ================= GŁÓWNA LOGIKA =================

def run():
    check_results()
    # Wyślij raport tygodniowy tylko w niedzielę wieczorem
    if datetime.now().weekday() == 6 and datetime.now().hour == 21:
        send_weekly_report()

    now = datetime.now(timezone.utc)
    coupons_db = load_coupons()
    sent_ids = [m["id"] for c in coupons_db for m in c["matches"]]
    
    leagues_pools = {}

    for sport_key, sport_label in SPORTS_CONFIG.items():
        matches_data = None
        for key in API_KEYS:
            try:
                r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/",
                    params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code == 200:
                    matches_data = r.json()
                    break
            except: continue

        if not matches_data: continue

        for m in matches_data:
            if m["id"] in sent_ids or len(m.get("bookmakers", [])) < MIN_BOOKMAKERS: continue
            
            m_dt_utc = datetime.fromisoformat(m["commence_time"].replace('Z', '+00:00'))
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
            avg_h, var_h = sum(h_odds)/len(h_odds), (max(h_odds)-min(h_odds))/(sum(h_odds)/len(h_odds))
            avg_a, var_a = sum(a_odds)/len(a_odds), (max(a_odds)-min(a_odds))/(sum(a_odds)/len(a_odds))

            pick = None
            if MIN_SINGLE_ODD <= avg_h <= MAX_SINGLE_ODD and var_h <= MAX_VARIANCE:
                pick = {"id": m["id"], "team": home, "odd": avg_h, "league": sport_label, "sport_key": sport_key, "vs": away, "golden": avg_h <= GOLDEN_MAX_ODD, "dropping": (avg_h - min(h_odds)) > 0.05, "date": m_dt_utc}
            elif MIN_SINGLE_ODD <= avg_a <= MAX_SINGLE_ODD and var_a <= MAX_VARIANCE:
                pick = {"id": m["id"], "team": away, "odd": avg_a, "league": sport_label, "sport_key": sport_key, "vs": home, "golden": avg_a <= GOLDEN_MAX_ODD, "dropping": (avg_a - min(a_odds)) > 0.05, "date": m_dt_utc}

            if pick:
                if sport_label not in leagues_pools: leagues_pools[sport_label] = []
                leagues_pools[sport_label].append(pick)

    # Parowanie i wysyłka
    all_picks = []
    for l in leagues_pools:
        leagues_pools[l].sort(key=lambda x: (x['golden'], x['dropping']), reverse=True)
        all_picks.extend(leagues_pools[l])
    all_picks.sort(key=lambda x: (x['golden'], x['dropping']), reverse=True)

    while len(all_picks) >= 2:
        p1 = all_picks.pop(0)
        p2_idx = next((i for i, x in enumerate(all_picks) if x['league'] != p1['league']), -1)
        
        if p2_idx != -1:
            p2 = all_picks.pop(p2_idx)
            is_super = p1['golden'] and p2['golden']
            stake = STAKE_GOLDEN if is_super else STAKE_STANDARD
            ako = round(p1['odd'] * p2['odd'], 2)
            ret = round(stake * TAX_RATE * ako, 2)
            
            msg = f"{'🌟 **ZŁOTY DOUBLE**' if is_super else '🚀 **KUPON DOUBLE**'}\n━━━━━━━━━━━━━━━\n1️⃣ {p1['league']}: **{p1['team']}** ({p1['odd']:.2f})\n2️⃣ {p2['league']}: **{p2['team']}** ({p2['odd']:.2f})\n━━━━━━━━━━━━━━━\nAKO: `{ako:.2f}` | ZYSK: `{round(ret-stake, 2)} PLN`"
            send_msg(msg)
            
            coupons_db.append({
                "status": "pending", "stake": stake, "potential_win": ret, "sport_key": p1["sport_key"],
                "end_time": max(p1["date"], p2["date"]).isoformat(),
                "matches": [{"id": p1['id'], "picked_team": p1['team'], "team": p1['team']}, {"id": p2['id'], "picked_team": p2['team'], "team": p2['team']}]
            })
        else: break
    save_coupons(coupons_db)

if __name__ == "__main__":
    run()
