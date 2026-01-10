import json
import os
import requests
from collections import defaultdict

# ================= KONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

# ================= FUNKCJE =================
def load_coupons():
    """Ładuje zapisane kupony z pliku JSON"""
    if os.path.exists(COUPONS_FILE):
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def send_msg(txt):
    """Wysyła wiadomość na Telegram lub drukuje debug"""
    if not T_TOKEN or not T_CHAT_RESULTS:
        print("[DEBUG] Telegram skipped:\n", txt)
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
            json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"[DEBUG] Telegram error: {e}")

def generate_report():
    """Generuje raport per ligę z zyskami/stratami i statystyką trafień"""
    coupons = load_coupons()
    if not coupons:
        print("Brak typów w pliku.")
        return

    leagues = defaultdict(lambda: {"won":0,"lost":0,"stake":0,"profit":0,"total":0})

    for c in coupons:
        league = c.get("league","unknown")
        status = c.get("status","pending")
        stake = c.get("stake",0)
        odds = c.get("odds",0)
        leagues[league]["total"] += 1
        leagues[league]["stake"] += stake

        if status == "won":
            leagues[league]["won"] += 1
            leagues[league]["profit"] += stake*(odds-1)
        elif status == "lost":
            leagues[league]["lost"] += 1
            leagues[league]["profit"] -= stake

    report = "📊 <b>RAPORT PER LIGA</b>\n\n"
    for league, data in leagues.items():
        total = data["total"]
        won = data["won"]
        lost = data["lost"]
        profit = data["profit"]
        stake = data["stake"]
        hit_rate = int((won/total)*100) if total>0 else 0
        trend = "📈" if profit>0 else "📉" if profit<0 else "➖"

        report += (f"🏟️ <b>{league.upper()}</b>\n"
                   f"🎯 Trafienia: {won}/{total} ({hit_rate}%)\n"
                   f"💰 Wydane: {stake:.2f} PLN\n"
                   f"💵 Zysk/Strata: {profit:.2f} PLN {trend}\n\n")

    print(report)
    send_msg(report)

# ================= MAIN =================
if __name__ == "__main__":
    generate_report()