import json, os
from datetime import datetime, timezone, timedelta
from dateutil import parser
from collections import defaultdict
import requests

# CONFIG
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_STATS = os.getenv("T_CHAT_RESULTS") # Raporty idą na konto wyników
TAX_PL = 0.88

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_STATS: 
        print("Błąd: Brak TOKENA lub CHAT_ID dla statystyk")
        return
    try:
        url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
        payload = {"chat_id": T_CHAT_STATS, "text": txt, "parse_mode": "HTML"}
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Błąd wysyłania statystyk: {e}")

def generate_report(coupons, name, days):
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    # Filtrujemy tylko rozliczone mecze z ostatnich X dni
    settled = [c for c in coupons if c.get('status') in ['WON', 'LOST'] and parser.isoparse(c['date']) >= start_date]
    
    if not settled:
        return f"📊 <b>Raport {name}</b>\nStatus: System czuwa. W tym okresie nie rozliczono jeszcze nowych meczów."

    stats = defaultdict(lambda: {"stake": 0, "ret": 0, "count": 0})
    for c in settled:
        ln = c.get('league_name', 'Inne')
        stats[ln]["stake"] += c['stake']
        stats[ln]["count"] += 1
        if c['status'] == 'WON': 
            stats[ln]["ret"] += (c['stake'] * c['odds'] * TAX_PL)

    msg = f"<b>📊 RAPORT {name.upper()} (NETTO -12%)</b>\n"
    msg += f"<code>{'LIGA':<10} | {'ZYSK':<6} | {'YIELD'}</code>\n"
    
    total_stake = 0
    total_ret = 0
    
    for ln, d in sorted(stats.items(), key=lambda x: x[1]["ret"]-x[1]["stake"], reverse=True):
        profit = d["ret"] - d["stake"]
        yield_perc = (profit / d["stake"] * 100)
        total_stake += d["stake"]
        total_ret += d["ret"]
        msg += f"<code>{ln[:10]:<10} | {profit:>+6.1f} | {yield_perc:>4.1f}%</code>\n"
    
    total_profit = total_ret - total_stake
    msg += f"\n💰 Łączny zysk netto: <b>{round(total_profit, 2)}j</b>"
    
    # AI REKOMENDACJE
    rec = "\n\n<b>💡 AI REKOMENDACJE:</b>\n"
    found_rec = False
    for ln, d in stats.items():
        if d["count"] >= 3:
            y = ((d["ret"]-d["stake"])/d["stake"]*100)
            if y > 2: 
                rec += f"🟢 {ln}: Wysoka skuteczność! ({y:.1f}%)\n"
                found_rec = True
            elif y < 0: 
                rec += f"🔴 {ln}: Podatek utrudnia zysk ({y:.1f}%)\n"
                found_rec = True
    
    return msg + (rec if found_rec else "")

if __name__ == "__main__":
    print("📊 Generowanie raportów...")
    if os.path.exists("coupons.json"):
        with open("coupons.json", "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except:
                data = []
    else:
        data = []
        
    # Zawsze wysyłaj raport dzienny
    report_day = generate_report(data, "Dzienny", 1)
    send_msg(report_day)
    
    # W poniedziałki raport tygodniowy
    if datetime.now().weekday() == 0:
        report_week = generate_report(data, "Tygodniowy", 7)
        send_msg(report_week)
    print("🏁 Raporty wysłane.")
