import json
from collections import defaultdict

RESULTS_FILE = "results.json"

def load_results():
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    results = load_results()
    league_stats = defaultdict(lambda: {"bets": 0, "profit": 0})
    for r in results:
        sport = r["match"].split()[0]  # uproszczone przypisanie ligi
        league_stats[sport]["bets"] += 1
        league_stats[sport]["profit"] += r["profit"]

    print("📊 RANKING LIG")
    print("━━━━━━━━━━━━━━━━━━━━")
    print("Liga       Bets   ROI    Profit")
    print("━━━━━━━━━━━━━━━━━━━━")
    for league, stats in league_stats.items():
        roi = (stats["profit"] / stats["bets"])*100 if stats["bets"] else 0
        emoji = "✅" if roi > 0 else "❌"
        print(f"{league:<10} {stats['bets']:<5} {roi:+.1f}%   {stats['profit']:+.0f} {emoji}")

if __name__ == "__main__":
    main()