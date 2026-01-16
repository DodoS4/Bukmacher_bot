import json
from datetime import datetime, timedelta

RESULTS_FILE = "results.json"
BANKROLL_FILE = "bankroll.json"

# ================= KONFIGURACJA =================
BR_START = 1000.0  # startowy bankroll
STAKE_PERCENT = 0.02  # 1.5–2% BR na zakład

# ================= FUNKCJE =================
def load_results():
    try:
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def update_bankroll(results):
    bankroll = BR_START
    for r in results:
        stake = bankroll * STAKE_PERCENT
        if r["status"] == "win":
            bankroll += stake * (r["odds"] - 1)
        elif r["status"] == "lose":
            bankroll -= stake
    return bankroll

def ranking_lig(results, days=30):
    cutoff = datetime.utcnow() - timedelta(days=days)
    leagues = {}
    for r in results:
        match_time = datetime.fromisoformat(r["commence_time"].replace("Z","+00:00"))
        if match_time < cutoff:
            continue
        sport = r["sport"]
        if sport not in leagues:
            leagues[sport] = {"bets":0,"profit":0.0}
        stake = BR_START * STAKE_PERCENT
        leagues[sport]["bets"] += 1
        if r["status"] == "win":
            leagues[sport]["profit"] += stake * (r["odds"] - 1)
        elif r["status"] == "lose":
            leagues[sport]["profit"] -= stake

    ranking = []
    for sport, v in leagues.items():
        roi = (v["profit"] / (v["bets"]*BR_START*STAKE_PERCENT)) * 100 if v["bets"] > 0 else 0
        ranking.append({"league":sport,"bets":v["bets"],"roi":roi,"profit":v["profit"]})

    ranking.sort(key=lambda x:x["profit"], reverse=True)
    return ranking

def print_reports():
    results = load_results()
    bankroll = update_bankroll(results)
    print(f"💰 Bankroll: {bankroll:.2f} zł")
    print(f"📊 Ranking lig – ostatnie 30 dni")
    print("Liga\tBets\tROI\tProfit")
    for r in ranking_lig(results):
        status_icon = "✅" if r["profit"]>0 else "❌"
        print(f"{r['league']}\t{r['bets']}\t{r['roi']:.1f}%\t{r['profit']:.2f} zł {status_icon}")

# ================= MAIN =================
if __name__ == "__main__":
    print_reports()