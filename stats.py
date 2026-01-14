import json, os
from datetime import datetime, timedelta, timezone
import requests

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

# ================= HELPERS =================
def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS:
        print("[WARN] Brak tokena Telegram lub chat_id")
        return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
                      json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"})
    except:
        print("[ERROR] Nie udało się wysłać wiadomości")

def load_coupons():
    if not os.path.exists(COUPONS_FILE): return []
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def generate_report(period="daily"):
    coupons = load_coupons()
    now = datetime.now(timezone.utc)

    # ================= OKRES CZASU =================
    if period=="daily":
        start = now - timedelta(days=1)
        title = f"📊 RAPORT DZIENNY – {start.date()} • {now.date()}"
    elif period=="weekly":
        start = now - timedelta(days=7)
        title = f"📊 RAPORT TYGODNIOWY – {start.date()} • {now.date()}"
    elif period=="monthly":
        start = now.replace(day=1)
        title = f"📊 RAPORT MIESIĘCZNY – {start.date()} • {now.date()}"
    else:
        start = now - timedelta(days=1)
        title = f"📊 RAPORT – {start.date()} • {now.date()}"

    # ================= FILTR =================
    filtered = []
    for c in coupons:
        try:
            c_date = datetime.fromisoformat(c["date"].replace("Z","+00:00"))
            if c_date >= start:
                filtered.append(c)
        except:
            continue

    total = len(filtered)
    won = sum(1 for c in filtered if c.get("status")=="WON")
    lost = sum(1 for c in filtered if c.get("status")=="LOST")
    pending = sum(1 for c in filtered if c.get("status")=="PENDING")
    profit = round(sum(c.get("profit",0) for c in filtered if c.get("profit") is not None),2)

    # ================= ROZKŁAD LIG =================
    leagues = {}
    for c in filtered:
        l = c.get("league","Other")
        if l not in leagues:
            leagues[l] = {"bets":0,"won":0,"lost":0,"profit":0}
        leagues[l]["bets"] +=1
        if c.get("status")=="WON":
            leagues[l]["won"] +=1
            leagues[l]["profit"] += c.get("profit",0)
        elif c.get("status")=="LOST":
            leagues[l]["lost"] +=1
            leagues[l]["profit"] += c.get("profit",0)

    # ================= TEKST =================
    msg = [title, "━━━━━━━━━━━━━━━━━━━━",
           f"🏆 Łącznie zakładów: {total}",
           f"✅ Wygrane: {won}",
           f"❌ Przegrane: {lost}",
           f"⏳ Pending: {pending}",
           f"💰 Zysk/Strata: {profit:+,.2f} zł",
           "━━━━━━━━━━━━━━━━━━━━",
           "📊 Rozkład na ligi:"]
    
    for l, data in leagues.items():
        total_bets = data["bets"]
        won_bets = data["won"]
        lost_bets = data["lost"]
        league_profit = round(data["profit"],2)
        # prosty wykres procentowy
        percent = int((won_bets/total_bets)*10) if total_bets>0 else 0
        bar = "▓"*percent + "░"*(10-percent)
        msg.append(f"{l:<15} │ Bets: {total_bets:<3} │ ✅ {won_bets:<3} │ ❌ {lost_bets:<3} │ 💰 {league_profit:+,.2f} zł │ {bar}")

    full_msg = "\n".join(msg)
    send_msg(full_msg)
    print(full_msg)

# ================= MAIN =================
if __name__ == "__main__":
    # generuj wszystkie trzy raporty
    for period in ["daily","weekly","monthly"]:
        generate_report(period)