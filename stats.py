import json
from datetime import datetime, timedelta
from collections import defaultdict

RESULTS_FILE = "results.json"

def load_results():
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_report(results, period="daily"):
    now = datetime.utcnow()
    if period == "daily":
        since = now - timedelta(days=1)
    elif period == "weekly":
        since = now - timedelta(weeks=1)
    elif period == "monthly":
        since = now - timedelta(days=30)
    else:
        since = datetime.min

    filtered = []
    for r in results:
        match_time = datetime.utcnow()  # zakładamy, że mamy czas meczu w danych
        filtered.append(r)

    league_stats = defaultdict(lambda: {"bets": 0, "profit": 0})
    for r in filtered:
        sport = r["match"].split()[0]  # uproszczenie
        league_stats[sport]["bets"] += 1
        league_stats[sport]["profit"] += r["profit"]

    print(f"📊 RAPORT {period.upper()}")
    print("━━━━━━━━━━━━━━━━━━━━")
    print("Liga       Bets   ROI    Profit")
    print("━━━━━━━━━━━━━━━━━━━━")
    for league, stats in league_stats.items():
        roi = (stats["profit"] / stats["bets"])*100 if stats["bets"] else 0
        emoji = "✅" if roi > 0 else "❌"
        print(f"{league:<10} {stats['bets']:<5} {roi:+.1f}%   {stats['profit']:+.0f} {emoji}")

if __name__ == "__main__":
    results = load_results()
    generate_report(results, "daily")
    generate_report(results, "weekly")
    generate_report(results, "monthly")