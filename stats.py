import json
import os
import requests
from collections import defaultdict
from datetime import datetime, timezone

# ================= KONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"
TOP_MATCHES_COUNT = 5  # liczba najważniejszych meczów w raporcie

# Mapowanie lig na flagi i skróty
LEAGUE_FLAGS = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "🇩🇪 Bundesliga",
    "soccer_italy_serie_a": "🇮🇹 Serie A"
}

# ================= FUNKCJE =================
def load_coupons():
    """Ładuje zapisane kupony z pliku JSON"""
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def send_msg(txt):
    """Wysyła wiadomość na Telegram lub drukuje debug"""
    if not T_TOKEN or not T_CHAT_RESULTS:
        print("[DEBUG] Telegram skipped:\n", txt)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[DEBUG] Telegram error: {e}")

def generate_daily_report():
    """Generuje raport dzienny z podsumowaniem per ligę i top meczami"""
    coupons = load_coupons()
    if not coupons:
        print("Brak typów w pliku.")
        return

    now = datetime.now(timezone.utc)
    bankroll = sum(c.get("stake",0)*(c.get("odds",0)-1) if c["status"]=="won" else -c.get("stake",0)
                   for c in coupons if "date_time" not in c or datetime.fromisoformat(c.get("date_time","2100-01-01T00:00:00+00:00")) <= now)
    
    # Podsumowanie per liga
    leagues = defaultdict(lambda: {"won":0,"lost":0,"total":0,"profit":0.0})
    for c in coupons:
        league = c.get("league","unknown")
        status = c.get("status","pending")
        stake = c.get("stake",0)
        odds = c.get("odds",0)
        leagues[league]["total"] += 1
        if status=="won":
            leagues[league]["won"] += 1
            leagues[league]["profit"] += stake*(odds-1)
        elif status=="lost":
            leagues[league]["lost"] += 1
            leagues[league]["profit"] -= stake

    # Budowa raportu
    msg = f"📊 <b>DAILY REPORT • {now.date()}</b>\n💰 Bankroll: {bankroll:.2f} PLN\n\n"

    for league, data in leagues.items():
        total = data["total"]
        won = data["won"]
        lost = data["lost"]
        profit = data["profit"]
        hit_rate = int((won/total)*100) if total>0 else 0
        bar_len = 8
        win_bar = int(bar_len * hit_rate / 100)
        lose_bar = bar_len - win_bar
        bar = "█"*win_bar + "░"*lose_bar
        emoji = "🔥" if profit>=0 else "❌"
        league_name = LEAGUE_FLAGS.get(league, league.upper())
        msg += f"{emoji} {league_name} | Typy: {total} | Wygrane: {won} | Przegrane: {lost} | Hit rate: {hit_rate}%\n"
        msg += f"{bar} | Zysk/Strata: {profit:.2f} PLN\n\n"

    # Najważniejsze mecze dnia - top 5 po stawce
    today_matches = [c for c in coupons if c.get("status") in ("won","lost")]
    today_matches.sort(key=lambda x: x.get("stake",0), reverse=True)
    top_matches = today_matches[:TOP_MATCHES_COUNT]

    if top_matches:
        msg += "🏟️ Najważniejsze mecze dnia:\n"
        for m in top_matches:
            status_emoji = "✅" if m.get("status")=="won" else "❌"
            msg += f" • {m.get('home','?')} vs {m.get('away','?')} | Typ: {m.get('pick','?')} | Stawka: {m.get('stake',0):.2f} PLN | {status_emoji}\n"

    print(msg)
    send_msg(msg)

# ================= MAIN =================
if __name__ == "__main__":
    generate_daily_report()