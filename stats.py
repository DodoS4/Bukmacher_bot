import json, os

COUPONS_FILE = "coupons_notax.json"

def run_stats():
    if not os.path.exists(COUPONS_FILE):
        return

    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        coupons = json.load(f)

    bets = [c for c in coupons if c["status"] in ("WON", "LOST")]
    if not bets:
        print("Brak danych.")
        return

    stake = sum(c["stake"] for c in bets)
    profit = sum(
        (c["stake"] * c["odds"] - c["stake"]) if c["status"] == "WON"
        else -c["stake"]
        for c in bets
    )

    roi = (profit / stake) * 100

    print("=" * 40)
    print(f"Bety: {len(bets)}")
    print(f"Stawka: {stake:.2f} zł")
    print(f"Profit: {profit:.2f} zł")
    print(f"ROI: {roi:.2f}%")
    print("=" * 40)

if __name__ == "__main__":
    run_stats()