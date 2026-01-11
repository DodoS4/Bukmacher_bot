import json, os, argparse
from datetime import datetime, timezone, timedelta
from dateutil import parser
from collections import defaultdict
import requests

# CONFIG - Kierujemy raporty na drugie konto
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_STATS = os.getenv("T_CHAT_RESULTS") # Zmieniono z T_CHAT na T_CHAT_RESULTS
TAX_PL = 0.88

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_STATS: return
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                     json={"chat_id": T_CHAT_STATS, "text": txt, "parse_mode": "HTML"})
    except:
        pass

def generate_report(coupons, name, days):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    settled = [c for c in coupons if c.get('status') in ['WON', 'LOST'] and parser.isoparse(c['date']) >= start]
    
    if not settled:
        return f"📊 <b>Raport {name}</b>\nStatus: System czuwa. W ostatnich {days} dniach nie rozliczono jeszcze żadnych meczów spełniających kryteria podatkowe."

    stats = defaultdict(lambda: {"stake": 0, "ret": 0, "count": 0})
    for c in settled:
        ln = c.get('league_name', 'Inne')
        stats[ln]["stake"] += c['stake']
        stats[ln]["count"] += 1
        if c['status'] == 'WON': 
            stats[ln]["ret"] += (c['stake'] * c['odds'] * TAX_PL)

    msg = f"<b>📊 RAPORT {name.upper()} (NETTO -12%)</b>\n<code>{'LIGA':<10} | {'ZYSK':<6} | {'YIELD'}</code>\n"
    for ln, d in sorted(stats.items(), key=lambda x: x[1]["ret"]-x[1]["stake"], reverse=True):
        p = d["ret"] - d["stake"]
        y = (p/d["stake"]*100)
        msg += f"<code>{ln[:10]:<10} | {p:>+6.1f} | {y:>4.1f}%</code>\n"
    
    total_p = sum(d["ret"] - d["stake"] for d in stats.values())
    msg += f"\n💰 Łączny zysk netto: <b>{round(total_p, 2)}j</b>"
    
    rec = "\n\n<b>💡 AI REKOMENDACJE:</b>\n"
    for ln, d in stats.items():
        if d["count"] >= 5:
            y = ((d["ret"]-d["stake"])/d["stake"]*100)
            if y > 2: rec += f"🟢 {ln}: Zyskowna liga! ({y:.1f}%)\n"
            elif y < 0: rec += f"🔴 {ln}: Podatek zjada zysk ({y:.1f}%)\n"
    return msg + rec

if __name__ == "__main__":
    if os.path.exists("coupons.json"):
        with open("coupons.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []
        
    # Wysyłaj raport dzienny zawsze na konto wynikowe
    send_msg(generate_report(data, "Dzienny", 1))
    
    # W poniedziałki wysyłaj dodatkowo raport tygdoniowy
    if datetime.now().weekday() == 0:
        send_msg(generate_report(data, "Tygodniowy", 7))
