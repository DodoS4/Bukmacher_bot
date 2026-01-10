import json, os, sys, requests
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

LEAGUE_FLAGS = {
    "basketball_nba": "🏀 NBA",
    "icehockey_nhl": "🏒 NHL",
    "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "⚽ Bundesliga",
    "soccer_italy_serie_a": "⚽ Serie A",
    "soccer_spain_la_liga": "⚽ La Liga",
    "soccer_france_ligue_one": "⚽ Ligue 1",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa",
    "basketball_euroleague": "🇪🇺 Euroliga",
    "soccer_uefa_champions_league": "🏆 Champions League",
    "americanfootball_nfl": "🏈 NFL"
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
    pending_count = 0
    
    for c in coupons:
        # Używamy added_at (data wysłania typu) lub date_time jako zapas
        dt_raw = c.get("added_at", c["date_time"])
        dt_str = dt_raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(dt_str)
        
        if dt >= start_period:
            period_coupons.append(c)
            if c["status"].upper() == "PENDING":
                pending_count += 1

    if not period_coupons:
        send_msg(f"📊 <b>{title}</b>\nBrak aktywności w wybranym okresie.")
        return

    league_stats = {}
    total_profit = 0
    
    for c in period_coupons:
        l_key = c.get("league", "inne")
        if l_key not in league_stats:
            league_stats[l_key] = {"won":0, "lost":0, "total":0, "profit":0.0}
        
        status = c["status"].upper()
        if status != "PENDING":
            league_stats[l_key]["total"] += 1
            if status == "WON":
                league_stats[l_key]["won"] += 1
                profit = (c["possible_win"] - c["stake"])
                league_stats[l_key]["profit"] += profit
                total_profit += profit
            elif status == "LOST":
                league_stats[l_key]["lost"] += 1
                league_stats[l_key]["profit"] -= c["stake"]
                total_profit -= c["stake"]

    msg = f"📊 <b>{title} • {now.strftime('%Y-%m-%d')}</b>\n"
    msg += f"🏦 Stan konta: <b>{bankroll:.2f} PLN</b>\n"
    msg += f"🏁 Wynik okresu: <b>{total_profit:+.2f} PLN</b>\n\n"

    for l_key, data in league_stats.items():
        total = data["total"]
        if total == 0: continue
        
        hit_rate = int((data["won"] / total) * 100)
        profit = data["profit"]
        trend = "📈" if profit >= 0 else "📉"
        
        bar_len = 8
        filled = int(bar_len * (hit_rate / 100))
        bar = "█" * filled + "░" * (bar_len - filled)
        
        league_name = LEAGUE_FLAGS.get(l_key, l_key)
        msg += f"{trend} <b>{league_name}</b> (Hit: {hit_rate}%)\n"
        msg += f"<code>{bar}</code> | <b>{profit:+.2f} PLN</b>\n\n"

    if pending_count > 0:
        msg += f"⏳ Oczekujące zakłady: <b>{pending_count}</b>\n"
    
    msg += "----------------------------------\n"
    msg += "🏟️ <b>Ostatnie rozliczenia:</b>\n"
    
    settled_matches = [m for m in period_coupons if m["status"].upper() != "PENDING"]
    sorted_matches = sorted(settled_matches, key=lambda x: x["date_time"], reverse=True)[:5]
    
    for m in sorted_matches:
        status_icon = "✅" if m["status"].upper() == "WON" else "❌"
        msg += f"{status_icon} {m['home']} - {m['away']} ({m['stake']} PLN)\n"

    send_msg(msg)

if __name__=="__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--daily"
    days = 7 if mode == "--weekly" else 30 if mode == "--monthly" else 1
    label = "WEEKLY REPORT" if mode == "--weekly" else "MONTHLY REPORT" if mode == "--monthly" else "DAILY REPORT"
    generate_report(days, label)
