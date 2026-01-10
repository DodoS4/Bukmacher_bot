import json, os
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
    "soccer_italy_serie_a": "⚽ Serie A"
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
    requests.post(
        f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
        json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"}
    )

def generate_report(period_days=1, title="DAILY REPORT"):
    coupons = load_json(COUPONS_FILE, [])
    bankroll_data = load_json(BANKROLL_FILE, {"bankroll": 0.0})
    bankroll = bankroll_data.get("bankroll", 0.0)
    
    now = datetime.now(timezone.utc)
    start_period = now - timedelta(days=period_days)

    # Filtrowanie i obliczenia
    period_coupons = []
    for c in coupons:
        dt = datetime.fromisoformat(c["date_time"].replace("Z", "+00:00"))
        if dt >= start_period:
            period_coupons.append(c)

    if not period_coupons:
        send_msg(f"📊 <b>{title}</b>\nBrak aktywności.")
        return

    league_stats = {}
    for c in period_coupons:
        l_key = c.get("league", "inne")
        if l_key not in league_stats:
            league_stats[l_key] = {"won":0, "lost":0, "total":0, "profit":0.0}
        
        if c["status"] != "pending":
            league_stats[l_key]["total"] += 1
            if c["status"] == "won":
                league_stats[l_key]["won"] += 1
                league_stats[l_key]["profit"] += (c["possible_win"] - c["stake"])
            else:
                league_stats[l_key]["lost"] += 1
                league_stats[l_key]["profit"] -= c["stake"]

    # Budowanie wiadomości
    msg = f"📊 <b>{title} • {now.strftime('%Y-%m-%d')}</b>\n"
    msg += f"💰 Bankroll: <b>{bankroll:.2f} PLN</b>\n\n"

    for l_key, data in league_stats.items():
        total = data["total"]
        if total == 0: continue
        
        hit_rate = int((data["won"] / total) * 100)
        profit = data["profit"]
        trend = "🔥" if profit >= 0 else "❌"
        
        # Generowanie paska postępu (8 znaków)
        bar_len = 8
        filled = int(bar_len * (hit_rate / 100))
        bar = "█" * filled + "░" * (bar_len - filled)
        
        league_name = LEAGUE_FLAGS.get(l_key, l_key)
        msg += f"{trend} {league_name} | Typy: {total} | W: {data['won']} | P: {data['lost']} | Hit: {hit_rate}%\n"
        msg += f"<code>{bar}</code> | Zysk: <b>{profit:.2f} PLN</b>\n\n"

    # Najważniejsze mecze (ostatnie 5 rozliczonych)
    msg += "🏟️ <b>Najważniejsze mecze dnia:</b>\n"
    sorted_matches = sorted(period_coupons, key=lambda x: x["date_time"], reverse=True)[:5]
    for m in sorted_matches:
        status_icon = "✅" if m["status"] == "won" else "❌" if m["status"] == "lost" else "⏳"
        dt_obj = datetime.fromisoformat(m["date_time"].replace("Z", "+00:00"))
        msg += f"• {m['home']} vs {m['away']} | {m['pick']} | {m['stake']} PLN | {status_icon}\n"

    send_msg(msg)

if __name__=="__main__":
    import sys
    days = 7 if "--weekly" in sys.argv else 30 if "--monthly" in sys.argv else 1
    label = "WEEKLY REPORT" if "--weekly" in sys.argv else "MONTHLY REPORT" if "--monthly" in sys.argv else "DAILY REPORT"
    generate_report(days, label)
