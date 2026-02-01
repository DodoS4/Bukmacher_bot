import json
import os
import requests
from datetime import datetime, timedelta, timezone

HISTORY_FILE = "history.json"

def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def send_telegram(message):
    token = get_secret("T_TOKEN")
    chat = get_secret("T_CHAT")
    if not token or not chat: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": message, "parse_mode": "HTML"}
    try: requests.post(url, json=payload, timeout=15)
    except: pass

def generate_stats():
    if not os.path.exists(HISTORY_FILE): return

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
    if not history: return

    # --- OBLICZENIA ---
    total_profit = sum(m.get('profit', 0) for m in history)
    # Startowałeś z 5000 PLN zysku + 5000 bazy (według Twojego raportu 13789.06)
    # Dostosuj tę liczbę poniżej, aby bankroll się zgadzał:
    base_capital = 5000 
    bankroll = base_capital + total_profit
    
    wins = sum(1 for m in history if m.get('status') == 'WIN')
    losses = sum(1 for m in history if m.get('status') == 'LOSS')
    total_matches = wins + losses
    
    accuracy = (wins / total_matches * 100) if total_matches > 0 else 0
    total_staked = sum(m.get('stake', 0) for m in history if m.get('status') in ['WIN', 'LOSS'])
    yield_val = (total_profit / total_staked * 100) if total_staked > 0 else 0

    # Zysk z ostatnich 24h
    now = datetime.now(timezone.utc)
    last_24h_profit = 0
    for m in history:
        try:
            m_time = datetime.fromisoformat(m['time'].replace("Z", "+00:00"))
            if now - m_time < timedelta(hours=24):
                last_24h_profit += m.get('profit', 0)
        except: continue

    # --- BUDOWANIE RAPORTU ---
    report = [
        "📊 <b>STATYSTYKI</b>",
        "━━━━━━━━━━━━━━━",
        f"🏦 <b>BANKROLL:</b> {round(bankroll, 2)} PLN",
        f"💰 Zysk Total: {round(total_profit, 2)} PLN",
        f"📅 Ostatnie 24h: {'+' if last_24h_profit >=0 else ''}{round(last_24h_profit, 2)} PLN",
        f"🎯 Skuteczność: {round(accuracy, 1)}%",
        f"📈 Yield: {round(yield_val, 2)}%",
        "━━━━━━━━━━━━━━━",
        "📝 <b>OSTATNIE WYNIKI:</b>"
    ]

    # Ostatnie 10 meczów
    for m in reversed(history[-10:]):
        status = "✅" if m['status'] == 'WIN' else "❌" if m['status'] == 'LOSS' else "⚠️"
        score = f" | {m.get('score', '?-?')}"
        profit = f"{'+' if m.get('profit', 0) > 0 else ''}{m.get('profit', 0.0)}"
        report.append(f"{status} {m['home']} - {m['away']} | {score} | {profit}")

    report.append("━━━━━━━━━━━━━━━")
    
    send_telegram("\n".join(report))

if __name__ == "__main__":
    generate_stats()
