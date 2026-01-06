import requests
import json
import os
from datetime import datetime, timedelta, timezone
from dateutil import parser

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
API_KEYS = [os.getenv("ODDS_KEY"), os.getenv("ODDS_KEY_2")]

COUPONS_FILE = "coupons.json"
INITIAL_BANKROLL = 100.0
VALUE_THRESHOLD = 0.05

LEAGUE_INFO = {
    "icehockey_nhl": {"name": "NHL", "flag": "🏒"},
    "basketball_nba": {"name": "NBA", "flag": "🏀"},
    "soccer_poland_ekstraklasa": {"name": "Ekstraklasa", "flag": "🇵🇱"},
    "soccer_epl": {"name": "Premier League", "flag": "🏴󠁧󠁢󠁥󠁮󠁧󠁿"},
    "soccer_germany_bundesliga": {"name": "Bundesliga", "flag": "🇩🇪"}
}

# ================= MODUŁ STATYSTYK LIGI =================
def generate_league_stats():
    if not os.path.exists(COUPONS_FILE):
        return "Brak danych do analizy."
    
    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        coupons = json.load(f)
    
    settled = [c for c in coupons if c["status"] in ["won", "lost"]]
    if not settled:
        return "Brak rozliczonych meczów."

    stats = {}
    for c in settled:
        l_id = c.get("league", "unknown")
        if l_id not in stats:
            stats[l_id] = {"profit": 0, "staked": 0, "wins": 0, "total": 0}
        
        stake = float(c["stake"])
        win_val = float(c["win_val"])
        
        stats[l_id]["staked"] += stake
        stats[l_id]["profit"] += (win_val - stake)
        stats[l_id]["total"] += 1
        if c["status"] == "won":
            stats[l_id]["wins"] += 1

    report = "🏆 <b>RANKING SKUTECZNOŚCI LIG:</b>\n"
    # Sortowanie po zysku (najlepsze na górze)
    sorted_stats = sorted(stats.items(), key=lambda x: x[1]["profit"], reverse=True)

    for l_id, s in sorted_stats:
        l_name = LEAGUE_INFO.get(l_id, {"name": l_id})["name"]
        l_flag = LEAGUE_INFO.get(l_id, {"flag": "⚽"})["flag"]
        l_yield = round((s["profit"] / s["staked"] * 100), 1) if s["staked"] > 0 else 0
        l_acc = round((s["wins"] / s["total"] * 100), 1)
        
        icon = "🟢" if s["profit"] >= 0 else "🔴"
        report += (f"{l_flag} <b>{l_name}</b>\n"
                  f"   {icon} Zysk: <b>{round(s['profit'], 2)} PLN</b>\n"
                  f"   🎯 Yield: <b>{l_yield}%</b> | Skut: <b>{l_acc}%</b>\n")
    
    return report

# ================= RAPORT PORANNY =================
def send_daily_summary():
    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        coupons = json.load(f)
    
    settled = [c for c in coupons if c["status"] in ["won", "lost"]]
    total_profit = sum(float(c["win_val"]) - float(c["stake"]) for c in settled)
    current_bankroll = INITIAL_BANKROLL + total_profit
    
    status_icon = "🚀" if total_profit >= 0 else "📉"
    growth = round(((current_bankroll - INITIAL_BANKROLL) / INITIAL_BANKROLL) * 100, 1)
    
    msg = (f"📊 <b>PORANNY RAPORT FINANSOWY</b>\n\n"
           f"💰 Stan konta: <b>{round(current_bankroll, 2)} PLN</b>\n"
           f"{status_icon} Zysk całkowity: <b>{round(total_profit, 2)} PLN</b>\n"
           f"📈 Wzrost portfela: <b>{growth}%</b>\n"
           f"----------------------------\n"
           f"{generate_league_stats()}\n"
           f"<i>System automatycznie skaluje stawki Kelly'ego.</i>")
    
    send_msg(msg, target="results")

def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target == "results" else T_CHAT
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

# ... (reszta Twojej logiki run() oraz Kelly'ego pozostaje bez zmian)

if __name__ == "__main__":
    # Jeśli jest 8 rano, wyślij raport ze statystykami lig
    if datetime.now().hour == 8 and datetime.now().minute < 10:
        send_daily_summary()
    # Dalej idzie standardowe skanowanie lig...
