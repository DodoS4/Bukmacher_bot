import json
import os
import requests
from datetime import datetime, timedelta, timezone

# ================= PANCERNA KONFIGURACJA =================
def get_env_safe(name):
    """Pobiera zmienną i usuwa zbędne spacje."""
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val and len(str(val).strip()) > 0 else None

# Próbujemy pobrać token i ID czatu z różnych możliwych nazw
TOKEN = get_env_safe("T_TOKEN")
# Szukamy pod T_CHAT_STATS, T_CHAT lub TELEGRAM_CHAT_ID dla maksymalnej pewności
CHAT_STATS = get_env_safe("T_CHAT_STATS") or get_env_safe("T_CHAT") or get_env_safe("TELEGRAM_CHAT_ID")

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
                    # Filtrujemy ligi, których nie chcemy w statystykach (np. NBA)
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
        return False, "❌ Brak history.json"
        
    try:
        with open('history.json', 'r', encoding='utf-8') as f:
            history = json.load(f)
            print(f"📂 Wczytano {len(history)} wpisów z history.json")
    except Exception as e:
        print(f"❌ Błąd odczytu history: {e}")
        return False, f"❌ Błąd odczytu history: {e}"

    old_total_bets = 0
    if os.path.exists('stats.json'):
        try:
            with open('stats.json', 'r', encoding='utf-8') as f:
                old_total_bets = json.load(f).get('total_bets', 0)
        except: pass

    total_profit, total_turnover, profit_24h = 0.0, 0.0, 0.0
    wins, losses = 0, 0
    series_icons = []
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)

    for bet in history:
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
        except Exception as e:
            print(f"⚠️ Błąd danych meczu: {e}")

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

    # Tworzenie raportu tekstowego
    report = [
        "📊 <b>DASHBOARD STATYSTYK</b>",
        f"━━━━━━━━━━━━━━━",
        f"💰 <b>Zysk Total:</b> <code>{total_profit:.2f} PLN</code>",
        f"📅 <b>Ostatnie 24h:</b> <code>{profit_24h:+.2f} PLN</code>",
        f"🎯 <b>Skuteczność:</b> <code>{web_data['win_rate']}%</code> ({wins}/{total_bets})",
        f"📈 <b>Yield:</b> <code>{web_data['yield']}%</code>",
        f"🕒 <b>W grze:</b> <code>{upcoming}</code>",
        f"━━━━━━━━━━━━━━━",
        f"🔥 <b>Ostatnie:</b> {''.join(series_icons[-10:])}"
    ]

    return (diff > 0), "\n".join(report)

if __name__ == "__main__":
    print(f"🔑 Diagnostyka kluczy: TOKEN={'OK' if TOKEN else 'BRAK'}, CHAT={'OK' if CHAT_STATS else 'BRAK'}")
    
    should_send, text = generate_stats()
    
    if TOKEN and CHAT_STATS:
        print("📤 Wysyłanie raportu na Telegram...")
        try:
            res = requests.post(
                f"https://api.telegram.org/bot{TOKEN}/sendMessage", 
                json={"chat_id": CHAT_STATS, "text": text, "parse_mode": "HTML"},
                timeout=15
            )
            if res.status_code == 200:
                print("✅ Raport wysłany pomyślnie!")
            else:
                print(f"❌ Błąd Telegrama: {res.status_code} - {res.text}")
        except Exception as e:
            print(f"❌ Błąd połączenia: {e}")
    else:
        print("⚠️ Pominąłem wysyłkę Telegram (brak kluczy)")
