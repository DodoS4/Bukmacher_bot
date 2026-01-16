import json
from datetime import datetime, timedelta

RESULTS_FILE = "results.json"

def load_results():
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("[WARN] Brak pliku results.json")
        return []

def league_stats(days=30):
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    results = load_results()
    stats = {}

    for r in results:
        if "profit" not in r or "commence_time" not in r:
            continue
        try:
            match_time = datetime.fromisoformat(r["commence_time"])
            if match_time < since:
                continue
        except Exception:
            continue

        league = r["sport"]
        if league not in stats:
            stats[league] = {"bets": 0, "profit": 0}

        stats[league]["bets"] += 1
        stats[league]["profit"] += r.get("profit", 0)

    # Oblicz ROI
    for l in stats:
        b = stats[l]["bets"]
        p = stats[l]["profit"]
        stats[l]["roi"] = round((p / b) * 100 if b else 0, 2)

    return stats

def print_league_ranking(stats):
    print("\n📊 RANKING LIG – OSTATNIE 30 DNI")
    print("━━━━━━━━━━━━━━━━━━━━")
    print(f"{'Liga':<20} Bets   ROI     Profit")
    print("━━━━━━━━━━━━━━━━━━━━")
    for league, data in sorted(stats.items(), key=lambda x: x[1]["roi"], reverse=True):
        profit = int(data["profit"] * 1000)  # zakładając stake 1 jednostka = 1000 zł (przykład)
        roi = f"{data['roi']}%"
        status = "✅" if data["roi"] > 0 else "❌"
        print(f"{league:<20} {data['bets']:<5} {roi:<7} {profit:<8} {status}")
    print("━━━━━━━━━━━━━━━━━━━━\n")

if __name__ == "__main__":
    stats = league_stats(30)
    print_league_ranking(stats)