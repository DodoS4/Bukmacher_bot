import json, os, sys, requests
from datetime import datetime, timedelta, timezone

# ================= CONFIG =================
COUPONS_FILE = "coupons.json"
BANKROLL_FILE = "bankroll.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

LEAGUE_FLAGS = {
    "basketball_nba": "🏀 NBA", "icehockey_nhl": "🏒 NHL", "soccer_epl": "⚽ EPL",
    "soccer_germany_bundesliga": "⚽ Bundesliga", "soccer_italy_serie_a": "⚽ Serie A",
    "soccer_spain_la_liga": "⚽ La Liga", "soccer_france_ligue_one": "⚽ Ligue 1",
    "soccer_poland_ekstraklasa": "⚽ Ekstraklasa", "basketball_euroleague": "🇪🇺 Euroliga",
    "soccer_uefa_champions_league": "🏆 Champions League", "americanfootball_nfl": "🏈 NFL"
}

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS: return
    try: requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                     json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"})
    except: pass

def generate_report(period_days=1, title="DAILY REPORT"):
    coupons = load_json(COUPONS_FILE, [])
    bank_data = load_json(BANKROLL_FILE, {"bankroll": 0.0})
    bankroll = bank_data.get("bankroll", 0.0)
    
    now = datetime.now(timezone.utc)
    start_period = now - timedelta(days=period_days)

    period_coupons = []
    pending_count = 0
    best_edge_coupon = None

    for c in coupons:
        dt_raw = c.get("added_at", c["date_time"])
        dt = datetime.fromisoformat(dt_raw.replace("Z", "+00:00"))
        if dt >= start_period:
            period_coupons.append(c)
            if c["status"].upper() == "PENDING":
                pending_count += 1
            
            # Szukamy najwyższego trafionego Edge
            if c["status"].upper() == "WON":
                # Wyliczamy edge na podstawie danych z kuponu (jeśli nie był zapisany, liczymy z kursu)
                c_edge = c.get("edge", 0) # bot powinien mieć to w coupons.json
                if not best_edge_coupon or c_edge > best_edge_coupon.get("edge", 0):
                    best_edge_coupon = c

    if not period_coupons:
        send_msg(f"📊 <b>{title}</b>\nBrak aktywności.")
        return

    league_stats = {}
    total_profit = 0
    for c in period_coupons:
        l_key = c.get("league", "inne")
        if l_key not in league_stats: league_stats[l_key] = {"won":0, "lost":0, "total":0, "profit":0.0}
        
        status = c["status"].upper()
        if status != "PENDING":
            league_stats[l_key]["total"] += 1
            if status == "WON":
                league_stats[l_key]["won"] += 1
                p = (c["possible_win"] - c["stake"])
                league_stats[l_key]["profit"] += p
                total_profit += p
            elif status == "LOST":
                league_stats[l_key]["lost"] += 1
                league_stats[l_key]["profit"] -= c["stake"]
                total_profit -= c["stake"]

    msg = f"📊 <b>{title} • {now.strftime('%Y-%m-%d')}</b>\n"
    msg += f"🏦 Stan konta: <b>{bankroll:.2f} PLN</b>\n"
    msg += f"🏁 Wynik okresu: <b>{total_profit:+.2f} PLN</b>\n\n"

    # SEKCJA BEST EDGE
    if best_edge_coupon:
        msg += "🏆 <b>BEST EDGE DNIA:</b>\n"
        msg += f"🎯 {best_edge_coupon['home']} vs {best_edge_coupon['away']}\n"
        msg += f"📈 Kurs: <b>{best_edge_coupon['odds']}</b> | Zysk: <b>+{best_edge_coupon['possible_win']-best_edge_coupon['stake']:.2f} PLN</b>\n\n"

    for l_key, data in league_stats.items():
        if data["total"] == 0: continue
        hr = int((data["won"] / data["total"]) * 100)
        trend = "📈" if data["profit"] >= 0 else "📉"
        bar = "█" * int(8 * (hr/100)) + "░" * (8 - int(8 * (hr/100)))
        msg += f"{trend} <b>{LEAGUE_FLAGS.get(l_key, l_key)}</b> (Hit: {hr}%)\n<code>{bar}</code> | <b>{data['profit']:+.2f} PLN</b>\n\n"

    if pending_count > 0: msg += f"⏳ Oczekujące zakłady: <b>{pending_count}</b>\n"
    msg += "----------------------------------\n🏟️ <b>Ostatnie:</b>\n"
    
    settled = [m for m in period_coupons if m["status"].upper() != "PENDING"]
    for m in sorted(settled, key=lambda x: x["date_time"], reverse=True)[:5]:
        msg += f"{'✅' if m['status'].upper()=='WON' else '❌'} {m['home']} ({m['stake']} PLN)\n"

    send_msg(msg)

if __name__=="__main__":
    generate_report()
