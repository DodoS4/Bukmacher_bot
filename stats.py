import json
import os
from datetime import datetime, timedelta

HISTORY_FILE = "history.json"
COUPONS_FILE = "coupons.json"

def generate_stats():
    if not os.path.exists(HISTORY_FILE):
        print("❌ Brak pliku historii.")
        return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    
    if not history:
        print("ℹ️ Historia jest pusta.")
        return

    # --- OBLICZENIA ---
    total_profit = sum(m.get('profit', 0) for m in history)
    bankroll = 5000 + total_profit # Założyłem bazowe 5000, zmień jeśli startowałeś z inną kwotą
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    losses = sum(1 for m in history if m.get('status') == 'LOSS')
    total_matches = wins + losses
    
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(m.get('stake', 0) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    # Zysk z ostatnich 24h
    now = datetime.now()
    last_24h_profit = 0
    for m in history:
        try:
            m_time = datetime.fromisoformat(m['time'].replace("Z", "+00:00")).replace(tzinfo=None)
            if now - m_time < timedelta(hours=24):
                last_24h_profit += m.get('profit', 0)
        except: continue

    # --- BUDOWANIE RAPORTU ---
    report = []
    report.append("📊 <b>STATYSTYKI SYSTEMU</b>")
    report.append("━━━━━━━━━━━━━━━")
    report.append(f"🏦 <b>BANKROLL:</b> {round(bankroll, 2)} PLN")
    report.append(f"💰 Zysk Total: {round(total_profit, 2)} PLN")
    report.append(f"📅 Ostatnie 24h: {'+' if last_24h_profit >=0 else ''}{round(last_24h_profit, 2)} PLN")
    report.append(f"🎯 Skuteczność: {round(accuracy, 1)}%")
    report.append(f"📈 Yield: {round(yield_val, 2)}%")
    report.append("━━━━━━━━━━━━━━━")
    report.append("📝 <b>OSTATNIE WYNIKI:</b>")

    # Ostatnie 10 meczów
    for m in reversed(history[-10:]):
        status = "✅" if m['status'] == 'WIN' else "❌" if m['status'] == 'LOSS' else "⚠️"
        score = f" | {m['score']}" if 'score' in m else ""
        profit = f"{'+' if m['profit'] > 0 else ''}{m['profit']}"
        report.append(f"{status} {m['home']} - {m['away']}{score} | {profit}")

    report.append("━━━━━━━━━━━━━━━")
    
    final_msg = "\n".join(report)
    print(final_msg)
    
    # Jeśli chcesz wysyłać to na Telegram automatycznie, odkomentuj poniższe:
    # send_telegram(final_msg)

if __name__ == "__main__":
    generate_stats()
