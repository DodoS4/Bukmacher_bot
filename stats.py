import json
from datetime import datetime, timedelta
import os
import requests

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT_RESULTS")
FILE = "coupons.json"

def send(msg):
    requests.post(
        f"https://api.telegram.org/bot{T_TOKEN}/sendMessage",
        json={"chat_id": T_CHAT, "text": msg, "parse_mode": "HTML"},
        timeout=10,
    )

coupons = json.load(open(FILE, "r", encoding="utf-8"))

def report(days, title):
    since = datetime.now() - timedelta(days=days)
    data = [c for c in coupons if datetime.fromisoformat(c["date"]) >= since]

    win = sum(1 for c in data if c["status"] == "won")
    lost = sum(1 for c in data if c["status"] == "lost")
    pending = sum(1 for c in data if c["status"] == "pending")
    profit = round(sum(c.get("profit", 0) for c in data), 2)

    msg = (
        f"📊 <b>{title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Zakłady: {len(data)}\n"
        f"✅ Wygrane: {win}\n"
        f"❌ Przegrane: {lost}\n"
        f"⏳ Pending: {pending}\n"
        f"💰 Zysk/Strata: <b>{profit} zł</b>"
    )
    send(msg)

report(1, "RAPORT DZIENNY")
report(7, "RAPORT TYGODNIOWY")
report(30, "RAPORT MIESIĘCZNY")