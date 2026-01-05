import json
import os
from datetime import datetime, timezone, timedelta

# ================= KONFIGURACJA =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")

COUPONS_FILE = "coupons.json"
STAKE = 5.0

# ================= WYSYŁKA =================
def send_msg(text, target="types"):
    chat_id = T_CHAT_RESULTS if target=="results" else T_CHAT
    if not T_TOKEN or not chat_id:
        print("Brak T_TOKEN lub chat_id")
        return
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try:
        import requests
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode":"Markdown"}, timeout=15)
    except Exception as e:
        print("Błąd wysyłki:", e)

# ================= COUPONS =================
def load_coupons():
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE,"r",encoding="utf-8") as f:
                return json.load(f)
        except:
            return []
    return []

def save_coupons(coupons):
    with open(COUPONS_FILE,"w",encoding="utf-8") as f:
        json.dump(coupons[-500:], f, indent=4)

# ================= TESTOWA OFERTA =================
def send_test_offer():
    coupons = load_coupons()
    
    now = datetime.now(timezone.utc)
    match_dt = now + timedelta(hours=2)

    test_coupon = {
        "home": "Test FC",
        "away": "Demo United",
        "picked": "Test FC",
        "odds": 1.8,
        "stake": STAKE,
        "status": "pending",
        "date": match_dt.isoformat(),
        "win_val": round(1.8*STAKE,2),
        "league": "test_league"
    }
    coupons.append(test_coupon)
    save_coupons(coupons)

    match_dt_str = match_dt.strftime("%d-%m-%Y %H:%M UTC")
    text = (
        f"📊 *TESTOWA OFERTA* (TEST LEAGUE)\n"
        f"🏟️ {test_coupon['home']} vs {test_coupon['away']}\n"
        f"🕓 {match_dt_str}\n"
        f"✅ Twój typ: *{test_coupon['picked']}*\n"
        f"💰 Stawka: {STAKE} PLN\n"
        f"🎯 Kurs: {test_coupon['odds']}"
    )
    send_msg(text,target="types")

# ================= ROZLICZANIE =================
def check_results():
    coupons = load_coupons()
    updated=False
    now=datetime.now(timezone.utc)
    for c in coupons:
        if c.get("status")!="pending":
            continue
        match_dt = datetime.fromisoformat(c["date"])
        if now < match_dt + timedelta(hours=4):
            continue

        # Testowy wynik – zawsze wygrywa
        c["status"]="win"
        profit = round(c["win_val"]-c["stake"],2)
        match_dt_str = match_dt.strftime("%d-%m-%Y %H:%M UTC")
        text=f"✅ *KUPON ROZLICZONY*\n🏟️ {c['home']} vs {c['away']}\n🕓 {match_dt_str}\n🎯 Twój typ: {c['picked']}\n💰 Bilans: {profit:+.2f} PLN\n🎯 Kurs: {c['odds']}"
        send_msg(text,target="results")
        updated=True
    if updated:
        save_coupons(coupons)

# ================= START =================
def run():
    send_test_offer()
    check_results()

if __name__=="__main__":
    run()
