import json, os, argparse
from datetime import datetime, timezone, timedelta
from dateutil import parser
from collections import defaultdict
import requests

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")
# Podatek usunięty z obliczeń (mnożnik 1.0)
TAX_MULTIPLIER = 1.0 

COUPONS_FILE = "coupons.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def send_msg(txt):
    if not T_TOKEN or not T_CHAT: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                     json={"chat_id": T_CHAT, "text": txt, "parse_mode": "HTML"})
    except Exception as e:
        print(f"Błąd wysyłki Telegram: {e}")

def generate_report(coupons, period_name, days_back):
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days_back)
    
    # Filtrujemy kupony rozliczone (WON/LOST) z wybranego okresu
    settled = [
        c for c in coupons 
        if c.get('status') in ['WON', 'LOST'] 
        and parser.isoparse(c['date']) >= start_date
    ]
    
    if not settled:
        return f"📊 <b>Raport {period_name}</b>: Brak danych w tym okresie."

    stats = defaultdict(lambda: {"stake": 0, "ret": 0, "count": 0, "wins": 0})
    for c in settled:
        # Używamy nazwy ligi lub klucza
        name = c.get('league_name', c.get('league_key', 'Inne'))
        stats[name]["stake"] += c['stake']
        stats[name]["count"] += 1
        if c['status'] == 'WON':
            stats[name]["ret"] += (c['stake'] * c['odds'] * TAX_MULTIPLIER)
            stats[name]["wins"] += 1

    msg = f"<b>📊 RAPORT {period_name.upper()}</b>\n"
    msg += f"<code>{'LIGA':<12} | {'ZYSK':<7} | {'YIELD'}</code>\n"
    msg += "<code>" + "━" * 30 + "</code>\n"

    t_s = t_r = 0
    # Sortujemy ligi po zysku (od największego)
    sorted_leagues = sorted(stats.items(), key=lambda x: (x[1]["ret"] - x[1]["stake"]), reverse=True)

    for league, d in sorted_leagues:
        profit = d["ret"] - d["stake"]
        y_pct = (profit / d["stake"] * 100) if d["stake"] > 0 else 0
        w_pct = (d["wins"] / d["count"] * 100) if d["count"] > 0 else 0
        
        t_s += d["stake"]
        t_r += d["ret"]
        
        prefix = "+" if profit > 0 else ""
        msg += f"<code>{league[:12]:<12} | {prefix}{profit:>6.1f} | {y_pct:>4.0f}%</code>\n"

    t_profit = t_r - t_s
    t_yield = (t_profit / t_s * 100) if t_s > 0 else 0
    
    msg += "<code>" + "━" * 30 + "</code>\n"
    msg += f"💰 <b>ZYSK NETTO: {t_profit:.2f} PLN</b>\n"
    msg += f"📈 <b>YIELD: {t_yield:.1f}%</b> | Kupony: {len(settled)}"
    return msg

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--auto', action='store_true')
    args = parser.parse_args()

    data_coupons = load_json(COUPONS_FILE, [])
    current_time = datetime.now()

    if args.auto:
        # 1. Raport Dzienny - wysyłany zawsze przy wywołaniu o 07:00
        send_msg(generate_report(data_coupons, "Dzienny", 1))

        # 2. Raport Tygodniowy - wysyłany tylko w poniedziałki rano
        if current_time.weekday() == 0:
            send_msg(generate_report(data_coupons, "Tygodniowy", 7))

        # 3. Raport Miesięczny - wysyłany tylko 1-szego dnia miesiąca
        if current_time.day == 1:
            send_msg(generate_report(data_coupons, "Miesięczny", 30))
    else:
        # Ręczne uruchomienie bez flagi pokaże raport dzienny w konsoli
        print(generate_report(data_coupons, "Podgląd (24h)", 1))
