import json
import os
import requests
from datetime import datetime, timedelta, timezone

# --- KONFIGURACJA ---
TOKEN = os.getenv("T_TOKEN")
CHAT_STATS = os.getenv("T_CHAT_STATS")
STARTING_BANKROLL = 5000.0

def get_upcoming_count():
    count = 0
    now = datetime.now(timezone.utc)
    limit = now + timedelta(hours=12)
    filename = 'coupons.json'
    
    if not os.path.exists(filename):
        return 0
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            coupons = json.load(f)
            if isinstance(coupons, list):
                for coupon in coupons:
                    if "basketball_nba" in str(coupon.get('sport', '')).lower():
                        continue
                    time_str = coupon.get('time')
                    if time_str:
                        try:
                            event_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                            if now <= event_time <= limit:
                                count += 1
                        except:
                            continue
    except:
        pass
    return count

def generate_stats():
    print(f"🔍 Rozpoczynam generowanie statystyk... ({datetime.now().strftime('%H:%M:%S')})")
    
    if not os.path.exists('history.json'):
        print("❌ Błąd: Plik history.json nie istnieje!")
        return None, "❌ Brak history.json"
        
    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
            print(f"📂 Wczytano {len(history)} wpisów z history.json")
    except Exception as e:
        print(f"❌ Błąd odczytu history: {e}")
        return None, f"❌ Błąd odczytu history: {e}"

    old_total_bets = 0
    if os.path.exists('stats.json'):
        try:
            with open('stats.json', 'r', encoding='utf-8') as f:
                old_total_bets = json.load(f).get('total_bets', 0)
        except: pass

    total_profit, total_turnover, profit_24h = 0.0, 0.0, 0.0
    wins, losses = 0, 0
    processed_matches, series_icons = [], []
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    for bet in history:
        # Debugowanie filtrów
        if "basketball_nba" in str(bet.get('sport', '')).lower(): 
            continue
        if str(bet.get('status', '')).upper() == "VOID": 
            continue

        try:
            prof = float(bet.get('profit', 0))
            stk = float(bet.get('stake', 0))
            total_profit += prof
            total_turnover += stk
            
            icon = "✅" if prof > 0 else "❌"
            if prof > 0: wins += 1
            else: losses += 1
            series_icons.append(icon)

            b_time = bet.get('time') or bet.get('date')
            if b_time:
                try:
                    dt_obj = datetime.fromisoformat(b_time.replace("Z", "+00:00"))
                    if dt_obj > yesterday:
                        profit_24h += prof
                except: pass

            processed_matches.append(f"{icon} {bet.get('home')}-{bet.get('away')} | `{prof:+.2f} PLN`")
        except Exception as e:
            print(f"⚠️ Pominąłem mecz z powodu błędu danych: {e}")

    total_bets = wins + losses
    upcoming = get_upcoming_count()
    
    print(f"📊 Wyniki: Profit: {total_profit:.2f}, Bets: {total_bets}, Wins: {wins}, Losses: {losses}")

    web_data = {
        "total_profit": round(total_profit, 2),
        "profit_24h": round(profit_24h, 2),
        "yield": round((total_profit / total_turnover * 100) if total_turnover > 0 else 0, 2),
        "roi": round((total_profit / STARTING_BANKROLL * 100) if STARTING_BANKROLL > 0 else 0, 2),
        "turnover": round(total_turnover, 2),
        "win_rate": round((wins / total_bets * 100) if total_bets > 0 else 0, 1),
        "total_bets": total_bets,
        "upcoming_count": upcoming,
        "last_update": now.strftime("%H:%M:%S")
    }

    with open('stats.json', 'w', encoding='utf-8') as f:
        json.dump(web_data, f, indent=4)
        print("💾 Zapisano stats.json")

    diff = total_bets - old_total_bets
    print(f"📈 Nowych rozliczonych meczów: {diff}")

    report = [
        "📊 *DASHBOARD STATYSTYK*",
        f"💰 *Zysk Total:* `{total_profit:.2f} PLN`",
        f"🎯 *Skuteczność:* `{web_data['win_rate']}%` ({wins}/{total_bets})",
        f"🕒 *W grze:* `{upcoming}`",
        f"🔥 *Ostatnie:* {''.join(series_icons[-10:])}"
    ]

    return (diff > 0), "\n".join(report)

if __name__ == "__main__":
    print(f"🔑 Sprawdzam klucze: TOKEN={'OK' if TOKEN else 'BRAK'}, CHAT={'OK' if CHAT_STATS else 'BRAK'}")
    should_send, text = generate_stats()
    
    if TOKEN and CHAT_STATS:
        print("📤 Próbuję wysłać raport na Telegram...")
        res = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                     json={"chat_id": CHAT_STATS, "text": text, "parse_mode": "Markdown"})
        if res.status_code == 200:
            print("✅ Raport wysłany pomyślnie!")
        else:
            print(f"❌ Błąd Telegrama: {res.status_code} - {res.text}")
    else:
        print("⚠️ Pominąłem wysyłkę Telegram (brak kluczy w os.getenv)")
