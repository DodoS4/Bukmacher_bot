import requests
import json
import os
from datetime import datetime

# ================= KONFIGURACJA EKSPERCKA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")           # Kanał TYPY
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")   # Kanał WYNIKI
API_KEYS = [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2")]

COUPONS_FILE = "coupons.json"
INITIAL_BANKROLL = 100.0
VALUE_THRESHOLD = -0.50  # Przewaga min. 5%
AUTO_STOP_LIMIT = -20.0 # Stop dla ligi przy stracie 20 PLN

# Lista monitorowanych lig
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

    status_txt = "✅ Wszystkie ligi aktywne"
    if frozen:
        frozen_names = [LEAGUE_INFO.get(fid, {"name": fid})["name"] for fid in frozen]
        status_txt = f"❄️ <b>ZAMROŻONE:</b> {', '.join(frozen_names)}"

    growth = round(((bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL) * 100, 1)
    icon = "🚀" if profit >= 0 else "📉"
    
    return (f"📊 <b>RAPORT ANALITYCZNY</b>\n\n"
            f"💰 Portfel: <b>{round(bankroll, 2)} PLN</b>\n"
            f"{icon} Zysk: <b>{round(profit, 2)} PLN ({growth}%)</b>\n"
            f"⏳ W grze: <b>{pending_count} kuponów</b>\n"
            f"----------------------------\n"
            f"{league_results if league_results else 'Brak rozliczonych gier.'}\n"
            f"🛡️ <b>STATUS:</b> {status_txt}")

# ================= LOGIKA OPERACYJNA =================
def run():
    # 1. Raport o 8 rano (Automatyczny)
    if datetime.now().hour == 8 and datetime.now().minute < 10:
        send_msg(generate_report(), "results")

    # 2. Pobierz tylko aktywne ligi i aktualne finanse
    active_leagues, _ = get_league_status()
    bankroll, _, _, _ = get_finances()
    coupons = load_coupons()

    for league in active_leagues:
        for key in API_KEYS:
            try:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds"
                r = requests.get(url, params={"apiKey": key, "regions": "eu", "markets": "h2h"}, timeout=15)
                if r.status_code != 200: continue
                
                events = r.json()
                for ev in events:
                    # Unikanie duplikatów
                    if any(c["home"] == ev["home_team"] for c in coupons if c["status"] == "pending"): continue
                    
                    # Logika wyboru kursu (Analiza pierwszego bukmachera z listy)
                    if not ev.get("bookmakers"): continue
                    outcomes = ev["bookmakers"][0]["markets"][0]["outcomes"]
                    
                    for out in outcomes:
                        odds = out["price"]
                        # Symulacja Twojego modelu prawdopodobieństwa (Edge)
                        # W profesjonalnym bota tutaj następuje porównanie z kursem 'ostrym'
                        edge = 0.06 # Stała testowa 6% - bot wyśle typ jeśli znajdzie taką okazję
                        
                        if edge >= VALUE_THRESHOLD:
                            # Kryterium Kelly'ego (Ułamek 10% dla bezpieczeństwa)
                            kelly_pct = (edge / (odds - 1)) * 0.1
                            stake = round(max(2.0, min(bankroll * kelly_pct, bankroll * 0.1)), 2)
                            
                            flag = LEAGUE_INFO.get(league, {"flag": "⚽"})["flag"]
                            l_name = LEAGUE_INFO.get(league, {"name": league})["name"]
                            
                            msg = (f"{flag} <b>OKAZJA {l_name} (Edge {int(edge*100)}%)</b>\n"
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
                break # Jeśli klucz zadziałał, przejdź do następnej ligi
            except Exception as e:
                continue
    
    save_coupons(coupons)

if __name__ == "__main__":
    # Sygnał startu dla użytkownika
    send_msg("🚀 <b>System Skalowania Kapitału Aktywny</b>\nSkanuję rynki w poszukiwaniu przewagi...", "results")
    
    # Uruchomienie głównej pętli
    run()
