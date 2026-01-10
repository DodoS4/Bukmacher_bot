import json, os, sys
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

# Rozszerzona lista flag, aby pasowała do start.py
LEAGUE_FLAGS = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_italy_serie_a": "⚽ Serie A",
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_france_ligue_one": "⚽ Ligue 1"
}

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return default

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        print("[DEBUG] Telegram skipped")
        return
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"Błąd wysyłki: {e}")

def generate_report(period_days=1, title="DAILY REPORT"):
    coupons = load_json(COUPONS_FILE, [])
    bankroll_data = load_json(BANKROLL_FILE, {"bankroll": 0.0})
    bankroll = bankroll_data.get("bankroll", 0.0)
    
    now = datetime.now(timezone.utc)
    start_period = now - timedelta(days=period_days)

    period_coupons = []
    for c in coupons:
        # Bezpieczniejsza konwersja daty
        dt_str = c["date_time"].replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        if dt >= start_period:
            period_coupons.append(c)

    if not period_coupons:
        send_msg(f"📊 <b>{title}</b>\nBrak aktywności w wybranym okresie.")
        return

    league_stats = {}
    for c in period_coupons:
        l_key = c.get("league", "inne")
        if l_key not in league_stats:
            league_stats[l_key] = {"won":0, "lost":0, "total":0, "profit":0.0}
        
        # POPRAWKA: Sprawdzamy statusy wielkimi literami (zgodnie z settle.py)
        status = c["status"].upper()
        if status != "PENDING":
            league_stats[l_key]["total"] += 1
            if status == "WON":
                league_stats[l_key]["won"] += 1
                # Kwota possible_win ma już odliczony podatek z start.py
                league_stats[l_key]["profit"] += (c["possible_win"] - c["stake"])
            elif status == "LOST":
                league_stats[l_key]["lost"] += 1
                league_stats[l_key]["profit"] -= c["stake"]

    msg = f"📊 <b>{title} • {now.strftime('%Y-%m-%d')}</b>\n"
    msg += f"🏦 Stan konta: <b>{bankroll:.2f} PLN</b>\n\n"

    total_profit = 0
    for l_key, data in league_stats.items():
        total = data["total"]
        if total == 0: continue
        
        hit_rate = int((data["won"] / total) * 100)
        profit = data["profit"]
        total_profit += profit
        trend = "📈" if profit >= 0 else "📉"
        
        bar_len = 8
        filled = int(bar_len * (hit_rate / 100))
        bar = "█" * filled + "░" * (bar_len - filled)
        
        league_name = LEAGUE_FLAGS.get(l_key, l_key)
        msg += f"{trend} <b>{league_name}</b> (Hit: {hit_rate}%)\n"
        msg += f"<code>{bar}</code> | Zysk: <b>{profit:+.2f} PLN</b>\n\n"

    msg += f"🏁 Łączny wynik: <b>{total_profit:+.2f} PLN</b>\n"
    msg += "----------------------------------\n"
    msg += "🏟️ <b>Ostatnie rozliczenia:</b>\n"
    
    # Tylko rozliczone mecze do listy na dole
    settled_matches = [m for m in period_coupons if m["status"].upper() != "PENDING"]
    sorted_matches = sorted(settled_matches, key=lambda x: x["date_time"], reverse=True)[:5]
    
    for m in sorted_matches:
        status_icon = "✅" if m["status"].upper() == "WON" else "❌"
        msg += f"{status_icon} {m['home']} - {m['away']} ({m['stake']} PLN)\n"

    send_msg(msg)

if __name__=="__main__":
    days = 7 if "--weekly" in sys.argv else 30 if "--monthly" in sys.argv else 1
    label = "WEEKLY REPORT" if "--weekly" in sys.argv else "MONTHLY REPORT" if "--monthly" in sys.argv else "DAILY REPORT"
    generate_report(days, label)
