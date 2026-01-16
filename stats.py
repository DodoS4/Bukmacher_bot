import json
from datetime import datetime, timedelta

COUPON_FILE = "coupons.json"
RESULTS_FILE = "results.json"

BANKROLL_FILE = "bankroll.json"

def load_results():
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def load_bankroll():
    try:
        with open(BANKROLL_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("bankroll", 1000)
    except FileNotFoundError:
        return 1000

def save_bankroll(bankroll):
    with open(BANKROLL_FILE, "w", encoding="utf-8") as f:
        json.dump({"bankroll": bankroll}, f, ensure_ascii=False, indent=4)

def generate_stats(days=30):
    results = load_results()
    cutoff = datetime.utcnow() - timedelta(days=days)
    league_stats = {}

    for r in results:
        match_time = datetime.fromisoformat(r["commence_time"])
        if match_time < cutoff:
            continue
        league = r["league"]
        if league not in league_stats:
            league_stats[league] = {"bets":0, "profit":0}
        for o in r["settled_odds"]:
            stake = 20  # założony stały stake lub dynamiczny z BR
            league_stats[league]["bets"] += 1
            if o["result"] == "win":
                league_stats[league]["profit"] += stake * (o["price"] -1)
            else:
                league_stats[league]["profit"] -= stake

    # ROI i ranking
    report = []
    for league, s in league_stats.items():
        roi = (s["profit"] / (s["bets"]*20)) * 100 if s["bets"]>0 else 0
        report.append({
            "league": league,
            "bets": s["bets"],
            "profit": round(s["profit"],2),
            "roi": round(roi,2)
        })
    report.sort(key=lambda x: x["roi"], reverse=True)
    return report

def print_report(days=30):
    stats = generate_stats(days)
    print("📊 RANKING LIG – OSTATNIE {} DNI".format(days))
    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"{'Liga':<20} {'Bets':<6} {'ROI':<8} {'Profit'}")
    print("━━━━━━━━━━━━━━━━━━━━")
    for s in stats:
        emoji = "✅" if s["profit"]>0 else "❌"
        print(f"{s['league']:<20} {s['bets']:<6} {s['roi']:+}%" + f" {s['profit']} zł {emoji}")
    print("━━━━━━━━━━━━━━━━━━━━")
    # aktualizacja bankrolla
    bankroll = load_bankroll()
    total_profit = sum([s["profit"] for s in stats])
    bankroll += total_profit
    save_bankroll(bankroll)
    print(f"[INFO] Aktualny bankroll: {bankroll} zł")

if __name__ == "__main__":
    print_report(30)  # ostatnie 30 dni