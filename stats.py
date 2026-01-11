import json, os, argparse
from datetime import datetime, timezone, timedelta
from dateutil import parser
from collections import defaultdict
import requests

# Konfiguracja (pobierana z Twoich sekretów)
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
TAX_PL = 1.0 # lub 0.88

def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    return default

def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                 json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})

def generate_report(coupons, period_name, days_back):
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days_back)
    
    # Filtrowanie tylko rozliczonych kuponów z danego okresu
    settled = [c for c in coupons if c['status'] in ['WON', 'LOST'] and parser.isoparse(c['date']) >= start_date]
    
    if not settled:
        return f"📊 <b>Raport {period_name}</b>: Brak danych."

    stats = defaultdict(lambda: {"stake": 0, "ret": 0, "count": 0, "wins": 0})
    for c in settled:
        name = c.get('league_name', 'Inne')
        stats[name]["stake"] += c['stake']
        stats[name]["count"] += 1
        if c['status'] == 'WON':
            stats[name]["ret"] += (c['stake'] * c['odds'] * TAX_PL)
            stats[name]["wins"] += 1

    msg = f"<b>📊 RAPORT {period_name.upper()}</b>\n"
    msg += f"<code>{'LIGA':<12} | {'ZYSK':<7} | {'YIELD'}</code>\n"
    msg += "<code>" + "━" * 30 + "</code>\n"

    t_s = t_r = 0
    for league, d in stats.items():
        profit = d["ret"] - d["stake"]
        y_pct = (profit / d["stake"] * 100) if d["stake"] > 0 else 0
        w_pct = (d["wins"] / d["count"] * 100) if d["count"] > 0 else 0
        
        # Pasek skuteczności [■■■□□]
        bar = "■" * int(w_pct/20) + "□" * (5 - int(w_pct/20))
        
        t_s += d["stake"]
        t_r += d["ret"]
        
        prefix = "+" if profit > 0 else ""
        msg += f"<code>{league[:12]:<12} | {prefix}{profit:>6.1f} | {y_pct:>4.0f}%</code>\n"

    t_profit = t_r - t_s
    t_yield = (t_profit / t_s * 100) if t_s > 0 else 0
    msg += "<code>" + "━" * 30 + "</code>\n"
    msg += f"💰 <b>ZYSK: {t_profit:.2f} PLN</b>\n"
    msg += f"📈 <b>YIELD: {t_yield:.1f}%</b> | Kupony: {len(settled)}"
    return msg

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true')
    args = parser.parse_args()

    coupons = load_json("coupons.json", [])
    now = datetime.now()

    if args.auto:
        # 1. Raport Dzienny (zawsze o 07:00)
        send_msg(generate_report(coupons, "Dzienny", 1))

        # 2. Raport Tygodniowy (w poniedziałki rano)
        if now.weekday() == 0:
            send_msg(generate_report(coupons, "Tygodniowy", 7))

        # 3. Raport Miesięczny (pierwszego dnia miesiąca)
        if now.day == 1:
            send_msg(generate_report(coupons, "Miesięczny", 30))
