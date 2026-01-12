import json, os
from datetime import datetime, timedelta

# ================= CONFIG =================
T_TOKEN = os.getenv("T_TOKEN")
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
COUPONS_FILE = "coupons.json"

def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def send_msg(txt):
    if not T_TOKEN or not T_CHAT_RESULTS: return
    import requests
    try: requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", json={"chat_id": T_CHAT_RESULTS, "text": txt, "parse_mode": "HTML"})
    except: pass

def generate_stats():
    coupons = load_json(COUPONS_FILE, [])
    if not coupons: return

    # Filtrujemy tylko rozliczone (WON/LOST) z ostatnich 7 dni
    settled = [c for c in coupons if c.get("status") in ["WON", "LOST"]]
    pending = [c for c in coupons if c.get("status") == "PENDING"]
    
    if not settled:
        print("Brak rozliczonych kuponów do statystyk.")
        return

    total_stake = 0
    total_profit = 0
    wins = 0
    
    # Statystyki per liga
    league_stats = {}

    for c in settled:
        stake = c.get("stake", 100)
        odds = c.get("odds", 1.0)
        is_win = c.get("status") == "WON"
        
        # Oblicz zysk netto (z podatkiem 12%)
        profit = stake * (odds * 0.88 - 1) if is_win else -stake
        
        total_stake += stake
        total_profit += profit
        if is_win: wins += 1
        
        # Grupowanie po lidze
        l_name = c.get("league_name", "Inne")
        if l_name not in league_stats: league_stats[l_name] = 0
        league_stats[l_name] += profit

    hit_rate = (wins / len(settled)) * 100
    yield_val = (total_profit / total_stake) * 100

    # Tworzenie wiadomości
    msg = (f"📊 <b>RAPORT STATYSTYCZNY</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"✅ Trafione: <b>{wins}</b>\n"
           f"❌ Przegrane: <b>{len(settled) - wins}</b>\n"
           f"⏳ W grze: <b>{len(pending)}</b>\n\n"
           f"🎯 Skuteczność: <b>{hit_rate:.1f}%</b>\n"
           f"💰 Zysk netto: <b>{total_profit:.22g} zł</b>\n"
           f"💹 Yield: <b>{yield_val:.1f}%</b>\n"
           f"━━━━━━━━━━━━━━━━━━━━\n"
           f"🏆 <b>WYNIKI WG LIG:</b>\n")
    
    for league, prof in league_stats.items():
        icon = "📈" if prof >= 0 else "📉"
        msg += f"{icon} {league}: <b>{prof:.22g} zł</b>\n"

    send_msg(msg)

if __name__ == "__main__":
    generate_stats()
