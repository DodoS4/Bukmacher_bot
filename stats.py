import json
import os
from datetime import datetime, timedelta, timezone

# ================= KONFIGURACJA =================
HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"
STATS_FILE = "stats.json"
STARTING_BANKROLL = 5000.0  # Twoja realna kwota startowa

def generate_stats():
    # 1. Inicjalizacja bazowa
    stats = {
        "total_profit": 0.0,
        "total_bets": 0,
        "win_rate": 0.0,
        "yield": 0.0,
        "roi": 0.0,
        "turnover": 0.0,
        "profit_24h": 0.0,
        "upcoming_count": 0,
        "last_update": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "current_bankroll": STARTING_BANKROLL
    }

    # 2. Liczenie kuponów "w grze"
    if os.path.exists(COUPONS_FILE):
        try:
            with open(COUPONS_FILE, "r", encoding="utf-8") as f:
                coupons = json.load(f)
                stats["upcoming_count"] = len(coupons)
        except Exception as e:
            print(f"⚠️ Błąd odczytu coupons.json: {e}")

    # 3. Przetwarzanie historii (Zysk i Statystyki)
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
            
            if history and isinstance(history, list):
                total_profit = 0.0
                turnover = 0.0
                wins = 0
                now = datetime.now(timezone.utc)
                yesterday = now - timedelta(days=1)
                p_24h = 0.0

                for m in history:
                    profit = float(m.get('profit', 0))
                    stake = float(m.get('stake', 0))
                    
                    total_profit += profit
                    turnover += stake
                    if profit > 0:
                        wins += 1
                    
                    # Logika 24h z obsługą stref czasowych
                    try:
                        m_time_str = m.get('time', '').replace("Z", "+00:00")
                        m_time = datetime.fromisoformat(m_time_str)
                        if m_time > yesterday:
                            p_24h += profit
                    except:
                        continue

                stats["total_profit"] = round(total_profit, 2)
                stats["total_bets"] = len(history)
                stats["turnover"] = round(turnover, 2)
                stats["win_rate"] = round((wins / len(history) * 100), 1) if history else 0
                stats["yield"] = round((total_profit / turnover * 100), 1) if turnover > 0 else 0
                stats["roi"] = round((total_profit / STARTING_BANKROLL * 100), 1)
                stats["current_bankroll"] = round(STARTING_BANKROLL + total_profit, 2)
                stats["profit_24h"] = round(p_24h, 2)

        except Exception as e:
            print(f"❌ Krytyczny błąd w history.json: {e}")

    # 4. Zapis z wymuszeniem odświeżenia
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=4)
        print(f"✅ Statystyki zapisane o {stats['last_update']}")
        print(f"📈 Profit: {stats['total_profit']} | Mecze: {stats['total_bets']}")
    except Exception as e:
        print(f"🚫 Nie można zapisać stats.json! Sprawdź uprawnienia: {e}")

if __name__ == "__main__":
    generate_stats()
