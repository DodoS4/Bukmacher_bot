import json
import os
import requests
from datetime import datetime

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
BANKROLL_FILE = "bankroll.json"
TELEGRAM_TOKEN = os.getenv("T_TOKEN")
TELEGRAM_CHAT = os.getenv("T_CHAT_RESULTS")

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": TELEGRAM_CHAT, "text": message, "parse_mode": "HTML"})

def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return default
    return default

def get_day_name(date_str):
    days = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    return days[dt.weekday()]

def analyze_stats():
    history = load_json(HISTORY_FILE, [])
    br_data = load_json(BANKROLL_FILE, {"bankroll": 1000.0})
    
    if not history:
        print("Brak danych do analizy.")
        return

    total_bets = len(history)
    total_profit = sum([b['profit'] for b in history])
    
    # 1. Analiza wg Dni Tygodnia
    day_stats = {}
    # 2. Analiza wg Lig
    league_stats = {}
    # 3. Analiza wg Kursów
    odds_ranges = {"Niskie (1.5-1.8)": [], "Średnie (1.8-2.2)": [], "Wysokie (2.2-2.5)": []}

    for b in history:
        # Dni
        day = get_day_name(b['date'])
        if day not in day_stats: day_stats[day] = 0
        day_stats[day] += b['profit']
        
        # Ligi
        sport = b.get('sport', 'Inne')
        if sport not in league_stats:
            league_stats[sport] = {'wins': 0, 'total': 0, 'profit': 0}
        league_stats[sport]['total'] += 1
        league_stats[sport]['profit'] += b['profit']
        if b['win']: league_stats[sport]['wins'] += 1

        # Kursy
        o = b['odds']
        res = 1 if b['win'] else 0
        if o < 1.8: odds_ranges["Niskie (1.5-1.8)"].append(res)
        elif o < 2.2: odds_ranges["Średnie (1.8-2.2)"].append(res)
        else: odds_ranges["Wysokie (2.2-2.5)"].append(res)

    # --- BUDOWANIE RAPORTU ---
    msg = f"🧠 <b>ANALIZA SYSTEMOWA BOT-PRO</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🏦 Bankroll: <b>{br_data['bankroll']:.2f} PLN</b>\n"
    msg += f"💰 Zysk całkowity: <b>{total_profit:+.2f} PLN</b>\n\n"

    # Ranking Dni
    best_day = max(day_stats, key=day_stats.get)
    msg += f"📅 <b>NAJLEPSZY DZIEŃ:</b> <code>{best_day}</code>\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n\n"

    msg += f"🏆 <b>PERFORMANCE LIG:</b>\n"
    sorted_leagues = sorted(league_stats.items(), key=lambda x: x[1]['profit'], reverse=True)
    for league, s in sorted_leagues:
        icon = "🔥" if s['profit'] > 0 else "🧊"
        acc = (s['wins']/s['total'])*100
        msg += f"{icon} {league}: <b>{s['profit']:+.2f}</b> ({acc:.0f}%)\n"

    msg += f"\n📈 <b>SKUTECZNOŚĆ KURSÓW:</b>\n"
    for r_name, results in odds_ranges.items():
        if results:
            r_acc = (sum(results)/len(results))*100
            msg += f"• {r_name}: <b>{r_acc:.1f}%</b>\n"

    # Wnioski końcowe
    msg += f"\n💡 <b>REKOMENDACJE:</b>\n"
    msg += f"• Trzymaj się: <b>{sorted_leagues[0][0]}</b>\n"
    
    worst_day = min(day_stats, key=day_stats.get)
    if day_stats[worst_day] < 0:
        msg += f"• Uważaj na: <b>{worst_day}</b> (najniższe wyniki)\n"

    send_telegram(msg)

if __name__ == "__main__":
    analyze_stats()
