import requests
import os
import json
from datetime import datetime, timezone

COUPONS_FILE = "coupons.json"
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS")
SCORES_API_KEY = os.getenv("SCORES_KEY")  # Twój klucz do Score API

def load_coupons():
    try:
        with open(COUPONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        json.dump(coupons, f, ensure_ascii=False, indent=2)

def fetch_results(match):
    """
    Pobiera wynik meczu z Score API
    """
    try:
        url = f"https://api.scoreapi.com/v1/match?league={match['league']}&home={match['home']}&away={match['away']}&apiKey={SCORES_API_KEY}"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("home_score"), data.get("away_score")
    except Exception as e:
        print(f"[WARN] Nie udało się pobrać wyników {match['home']} vs {match['away']}: {e}")
        return None, None

def settle():
    coupons = load_coupons()
    updated = False

    for c in coupons:
        if c["status"] != "Pending":
            continue

        home_score, away_score = fetch_results(c)
        if home_score is None or away_score is None:
            continue  # nadal pending

        if (c["pick"] == c["home"] and home_score > away_score) or (c["pick"] == c["away"] and away_score > home_score):
            c["status"] = "✅ Wygrany"
        else:
            c["status"] = "❌ Przegrany"
        updated = True

    if updated:
        save_coupons(coupons)
        send_results_telegram(coupons)

def send_results_telegram(coupons):
    for c in coupons:
        if c["status"] == "Pending":
            continue
        text = f"🏀 {c['league']}\n{c['home']} 🆚 {c['away']}\n🎯 Typ: {c['pick']} ({c['type']})\n💸 Kurs: {c['odds']} | {c['status']}\n📅 {c['date']}"
        url = f"https://api.telegram.org/bot{T_CHAT_RESULTS}/sendMessage"
        try:
            requests.post(url, data={"chat_id": T_CHAT_RESULTS, "text": text})
        except Exception as e:
            print(f"[ERROR] Telegram: {e}")

if __name__ == "__main__":
    settle()