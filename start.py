import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= KONFIGURACJA (9.5/10) =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2")]

COUPONS_FILE = "coupons.json"
INITIAL_BANKROLL = 100.0
VALUE_THRESHOLD = 0.04  
AUTO_STOP_LIMIT = -20.0 

LEAGUES = [
    "icehockey_nhl", "basketball_nba", "soccer_poland_ekstraklasa",
    "soccer_epl", "soccer_germany_bundesliga", "soccer_uefa_champs_league"
]

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "🇵🇱"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"},
    "soccer_uefa_champs_league": {"name": "Champions League", "flag": "🏆"}
}

# ================= NARZĘDZIA DANYCH =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons[-2000:], f, indent=4)

def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    if not T_TOKEN or not chat_id: return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

# ================= ANALIZA I FILTROWANIE =================
def get_finances():
    coupons = load_coupons()
    settled = [c for c in coupons if c["status"] in ["won", "lost"]]
    pending = [c for c in coupons if c["status"] == "pending"]
    profit = sum(float(c["win_val"]) - float(c["stake"]) for c in settled)
    return INITIAL_BANKROLL + profit, profit, settled, len(pending)

def get_league_status():
    _, _, settled, _ = get_finances()
    active, frozen = [], []
    for l_id in LEAGUES:
        l_profit = sum(float(c["win_val"]) - float(c["stake"]) for c in settled if c.get("league") == l_id)
        if l_profit <= AUTO_STOP_LIMIT:
            frozen.append(l_id)
        else:
            active.append(l_id)
    return active, frozen

def generate_report():
    bankroll, profit, settled, pending_count = get_finances()
    active, frozen = get_league_status()
    
    # Statystyki lig
    stats = {}
    for c in settled:
        l_id = c.get("league", "unknown")
        if l_id not in stats: stats[l_id] = {"p": 0, "s": 0, "t": 0}
        stats[l_id]["p"] += (float(c["win_val"]) - float(c["stake"]))
        stats[l_id]["s"] += float(c["stake"])
        stats[l_id]["t"] += 1

    league_results = ""
    for l_id, s in sorted(stats.items(), key=lambda x: x[1]["p"], reverse=True):
        name = LEAGUE_INFO.get(l_id, {"name": l_id})["name"]
        l_yield = round((s["p"] / s["s"] * 100), 1) if s["s"] > 0 else 0
        icon = "🟢" if s["p"] >= 0 else "🔴"
        league_results += f"{icon} {name}: <b>{round(s['p'], 2)} PLN</b> ({l_yield}%)\n"

    # Status zamrożonych lig
    status_msg = "✅ Wszystkie ligi aktywne"
    if frozen:
        frozen_names = [LEAGUE_INFO.get(fid, {"name": fid})["name"] for fid in frozen]
        status_msg = f"❄️ <b>ZAMROŻONE:</b> {', '.join(frozen_names)}"

    growth = round(((bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL) * 100, 1)
    return (f"📊 <b>RAPORT ANALITYCZNY</b>\n\n"
            f"💰 Portfel: <b>{round(bankroll, 2)} PLN</b>\n"
            f"📈 Zysk: <b>{round(profit, 2)} PLN ({growth}%)</b>\n"
            f"⏳ W grze: <b>{pending_count} kuponów</b>\n"
            f"----------------------------\n"
            f"{league_results}\n"
            f"🛡️ <b>STATUS:</b> {status_icon(profit)} {status_msg}")

def status_icon(p): return "🚀" if p >= 0 else "📉"

# ================= LOGIKA OPERACYJNA =================
def run():
    # 1. Raport o 8 rano
    if datetime.now().hour == 8 and datetime.now().minute < 10:
        send_msg(generate_report(), "results")

    # 2. Pobierz tylko aktywne ligi
    active_leagues, _ = get_league_status()
    bankroll, _, _, _ = get_finances()
    coupons = load_coupons()

    for league in active_leagues:
        for key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
                r = requests.get(url, params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                
                for ev in r.json():
                    if any(c["home"] == ev["home_team"] for c in coupons): continue
                    
                    # Logika wyboru (Uproszczona pod Twój model)
                    outcomes = ev["bookmakers"][0]["markets"][0]["outcomes"]
                    for out in outcomes:
                        odds, edge = out["price"], 0.06 # Przykładowy Edge 6%
                        
                        if edge >= VALUE_THRESHOLD:
                            # Kryterium Kelly'ego
                            kelly_pct = (edge / (odds - 1)) * 0.1
                            stake = round(max(2.0, min(bankroll * kelly_pct, bankroll * 0.1)), 2)
                            
                            flag = LEAGUE_INFO.get(league, {"flag": "⚽"})["flag"]
                            msg = (f"{flag} <b>OKAZJA (Edge {int(edge*100)}%)</b>\n"
                                   f"🏟️ {ev['home_team']} - {ev['away_team']}\n"
                                   f"✅ Typ: <b>{out['name']}</b>\n"
                                   f"🎯 Kurs: <b>{odds}</b>\n"
                                   f"💰 Stawka: <b>{stake} PLN</b>")
                            
                            send_msg(msg)
                            coupons.append({
                                "home": ev["home_team"], "away": ev["away_team"],
                                "league": league, "stake": stake, "odds": odds,
                                "status": "pending", "win_val": 0, "picked": out["name"]
                            })
                break
            except: continue
    save_coupons(coupons)

if __name__ == "__main__":
    run()
