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
MIN_BOOKMAKERS = 7  # OPCJA 4: Filtr płynności

SPORTS_CONFIG = {
    "soccer_epl": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "soccer_spain_la_liga": "🇪🇸 La Liga",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga", "soccer_italy_serie_a": "🇮🇹 Serie A",
    "soccer_france_ligue_one": "🇫🇷 Ligue 1", "soccer_poland_ekstraklasa": "🇵🇱 Ekstraklasa",
    "soccer_netherlands_ere_divisie": "🇳🇱 Eredivisie", "soccer_portugal_primeira_liga": "🇵🇹 Primeira Liga",
    "soccer_uefa_champions_league": "🇪🇺 Liga Mistrzów", "soccer_uefa_europa_league": "🇪🇺 Liga Europy",
    "basketball_nba": "🏀 NBA"
}

COUPONS_FILE = "coupons.json"

# ================= SYSTEM BAZY I RAPORTÓW =================

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r") as f: return json.load(f)
    except: return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w") as f: json.dump(coupons[-500:], f)

def send_msg(text):
    if not T_TOKEN or not T_CHAT: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": T_CHAT, "text": text, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def check_results():
    coupons = load_coupons()
    updated = False
    now = datetime.now(timezone.utc)
    
    for c in coupons:
        if c.get("status") != "pending": continue
        end_time = datetime.fromisoformat(c["end_time"])
        if now > end_time + timedelta(hours=4):
            for key in API_KEYS:
                try:
                    r = requests.get(f"https://api.the-odds-api.com/v4/sports/{c['sport_key']}/scores/", 
                                     params={"apiKey": key, "daysFrom": 3}, timeout=15)
                    if r.status_code == 200:
                        scores = r.json()
                        matches_found, wins = 0, 0
                        for m_saved in c["matches"]:
                            for s in scores:
                                if s["id"] == m_saved["id"] and s.get("completed"):
                                    matches_found += 1
                                    h, a = (s["scores"][0]["score"], s["scores"][1]["score"]) if s["scores"] else (0,0)
                                    winner = s["home_team"] if int(h) > int(a) else (s["away_team"] if int(a) > int(h) else "Remis")
                                    if winner == m_saved["picked"]: wins += 1
                        
                        if matches_found == len(c["matches"]):
                            c["status"] = "win" if wins == len(c["matches"]) else "loss"
                            updated = True
                            icon = "✅" if c["status"] == "win" else "❌"
                            val = round(c['win_val'] - c['stake'], 2) if c["status"] == "win" else -c['stake']
                            send_msg(f"{icon} **KUPON ROZLICZONY**\nWynik: `{c['status'].upper()}`\nBilans: `{val:+.2f} PLN`")
                        break
                except: continue
    if updated: save_coupons(coupons)

def send_weekly_report():
    coupons = load_coupons()
    now = datetime.now(timezone.utc)
    week_data = [c for c in coupons if c["status"] != "pending" and (now - datetime.fromisoformat(c["end_time"])).days <= 7]
    if not week_data: return
    
    total_stake = sum(c["stake"] for c in week_data)
    total_win = sum(c["win_val"] for c in week_data if c["status"] == "win")
    profit = total_win - total_stake
    
    msg = (f"📅 **PODSUMOWANIE TYGODNIOWE**\n"
           f"━━━━━━━━━━━━━━━\n"
           f"Kupony: `{len(week_data)}` (✅ {len([x for x in week_data if x['status']=='win'])})\n"
           f"Zysk/Strata: `{profit:+.2f} PLN`\n"
           f"Yield: `{(profit/total_stake)*100:.2f}%`" if total_stake > 0 else "")
    send_msg(msg)

# ================= GŁÓWNA LOGIKA =================

def run():
    # OPCJA 5: Raport prawidłowego działania
    send_msg("⚙️ **SYSTEM AKTYWNY**: Rozpoczynam skanowanie rynków...")
    
    check_results()
    now_pl = datetime.now(timezone.utc) + timedelta(hours=1)
    if now_pl.weekday() == 6 and now_pl.hour == 21: send_weekly_report()

    coupons_db = load_coupons()
    sent_ids = [m["id"] for c in coupons_db for m in c["matches"]]
    leagues_pools = {}
    total_scanned = 0

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
        
        total_scanned += len(matches)
        for m in matches:
            if m["id"] in sent_ids or len(m.get("bookmakers", [])) < MIN_BOOKMAKERS: continue
            m_dt = datetime.fromisoformat(m["commence_time"].replace('Z', '+00:00'))
            if m_dt < datetime.now(timezone.utc) or m_dt > (datetime.now(timezone.utc) + timedelta(hours=48)): continue

            h, a = m["home_team"], m["away_team"]
            h_o, a_o = [], []
            for bm in m.get("bookmakers", []):
                for market in bm.get("markets", []):
                    if market["key"] == "h2h":
                        for o in market["outcomes"]:
                            if o["name"] == h: h_o.append(o["price"])
                            if o["name"] == a: a_o.append(o["price"])
            
            if len(h_o) < MIN_BOOKMAKERS: continue
            avg_h, avg_a = sum(h_o)/len(h_o), sum(a_o)/len(a_o)
            var_h, var_a = (max(h_o)-min(h_o))/avg_h, (max(a_o)-min(a_o))/avg_a

            pick = None
            if MIN_SINGLE_ODD <= avg_h <= MAX_SINGLE_ODD and var_h <= MAX_VARIANCE:
                pick = {"id": m["id"], "team": h, "odd": avg_h, "league": sport_label, "key": sport_key, "vs": a, "golden": avg_h <= GOLDEN_MAX_ODD, "picked": h, "date": m_dt}
            elif MIN_SINGLE_ODD <= avg_a <= MAX_SINGLE_ODD and var_a <= MAX_VARIANCE:
                pick = {"id": m["id"], "team": a, "odd": avg_a, "league": sport_label, "key": sport_key, "vs": h, "golden": avg_a <= GOLDEN_MAX_ODD, "picked": a, "date": m_dt}
            
            if pick:
                if sport_label not in leagues_pools: leagues_pools[sport_label] = []
                leagues_pools[sport_label].append(pick)

    # OPCJA 3: Inteligentne parowanie lig
    all_picks = []
    for l in leagues_pools:
        leagues_pools[l].sort(key=lambda x: x['golden'], reverse=True)
        all_picks.extend(leagues_pools[l])
    all_picks.sort(key=lambda x: x['golden'], reverse=True)

    while len(all_picks) >= 2:
        p1 = all_picks.pop(0)
        p2_idx = next((i for i, x in enumerate(all_picks) if x['league'] != p1['league']), -1)
        if p2_idx == -1: break
        p2 = all_picks.pop(p2_idx)
        
        ako = round(p1['odd'] * p2['odd'], 2)
        stake = STAKE_GOLDEN if (p1['golden'] and p2['golden']) else STAKE_STANDARD
        win_val = round(stake * TAX_RATE * ako, 2)
        
        msg = (f"{'🌟 **ZŁOTY DOUBLE**' if stake == STAKE_GOLDEN else '🚀 **KUPON DOUBLE**'}\n"
               f"━━━━━━━━━━━━━━━\n1️⃣ {p1['league']}: **{p1['team']}** (`{p1['odd']:.2f}`)\n"
               f"2️⃣ {p2['league']}: **{p2['team']}** (`{p2['odd']:.2f}`)\n"
               f"━━━━━━━━━━━━━━━\nAKO: `{ako:.2f}` | ZYSK: `{round(win_val-stake, 2)} PLN`")
        send_msg(msg)
        
        coupons_db.append({
            "status": "pending", "stake": stake, "win_val": win_val, "sport_key": p1["key"],
            "end_time": max(p1["date"], p2["date"]).isoformat(),
            "matches": [{"id": p1["id"], "picked": p1["picked"], "team": p1["team"]}, 
                        {"id": p2["id"], "picked": p2["picked"], "team": p2["team"]}]
        })
    
    save_coupons(coupons_db)
    send_msg(f"✅ **SKANOWANIE ZAKOŃCZONE**: Przeanalizowano `{total_scanned}` meczów.")

if __name__ == "__main__":
    run()
