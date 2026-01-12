import json, os
from datetime import datetime, timedelta
import requests
from collections import defaultdict

FILE = "coupons_notax.json"
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT_RESULTS")

def tg(msg):
    requests.post(
        f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
        json={"chat_id": T_CHAT, "text": msg, "parse_mode": "HTML"}
    )

with open(FILE, "r", encoding="utf-8") as f:
    data = json.load(f)

today = datetime.utcnow().date()

daily = [c for c in data if c["settled_at"] and
         datetime.fromisoformat(c["settled_at"]).date() == today]

if not daily:
    exit()

profit = sum(c["profit"] for c in daily)
stake = sum(c["stake"] for c in daily)
wins = len([c for c in daily if c["profit"] > 0])

msg = (
    f"📊 <b>DZIENNY RAPORT • NO TAX</b>\n"
    f"📅 {today}\n\n"
    f"🎯 Bety: {len(daily)}\n"
    f"✅ Wygrane: {wins}\n"
    f"❌ Przegrane: {len(daily)-wins}\n\n"
    f"💰 Profit: <b>{profit:.2f} zł</b>\n"
    f"📊 ROI: <b>{(profit/stake)*100:.2f}%</b>\n"
)

# --- LIGI ---
by_league = defaultdict(list)
for c in daily:
    by_league[c["league"]].append(c["profit"])

msg += "\n📈 <b>LIGI</b>\n"
for l, vals in by_league.items():
    msg += f"{l}: {sum(vals):.2f} zł\n"

# --- KELLY (symulacja 0.5x) ---
kelly_profit = 0
for c in daily:
    b = c["odds"] - 1
    p = 0.5  # uproszczone EV
    k = max((p*b - (1-p))/b, 0) * 0.5
    kelly_profit += c["profit"] * k

msg += f"\n📐 <b>Flat vs Kelly (sym)</b>\nFlat: {profit:.2f} zł\nKelly: ~{kelly_profit:.2f} zł"

tg(msg)