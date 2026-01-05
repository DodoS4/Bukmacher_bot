import json
import os
import requests

def send_msg(text):
    token = os.getenv("T_TOKEN")
    chat = os.getenv("T_CHAT")
    if token and chat:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat, "text": text, "parse_mode": "Markdown"})

def get_stats():
    if not os.path.exists("coupons.json"):
        return "❌ Brak pliku bazy danych (coupons.json)."

    with open("coupons.json", "r") as f:
        data = json.load(f)

    settled = [c for c in data if c["status"] in ["win", "loss"]]
    if not settled:
        return "info 📊 Brak rozliczonych kuponów do analizy."

    wins = [c for c in settled if c["status"] == "win"]
    total_staked = sum(c["stake"] for c in settled)
    total_returned = sum(c["win_val"] for c in wins)
    profit = total_returned - total_staked
    win_rate = (len(wins) / len(settled)) * 100
    yield_val = (profit / total_staked) * 100 if total_staked > 0 else 0

    msg = (f"📊 **STATYSTYKI BOTA**\n"
           f"━━━━━━━━━━━━━━━\n"
           f"Kupony: `{len(settled)}` (✅ `{len(wins)}` | ❌ `{len(settled)-len(wins)}`)\n"
           f"Skuteczność: `{win_rate:.1f}%`\n"
           f"Yield: `{yield_val:+.2f}%`\n"
           f"━━━━━━━━━━━━━━━\n"
           f"Suma stawek: `{total_staked:.2f} PLN`\n"
           f"Zysk/Strata: `{profit:+.2f} PLN` 💰")
    return msg

if __name__ == "__main__":
    report = get_stats()
    send_msg(report)
