import os
import requests

def get_secret(name):
    val = os.environ.get(name)
    return str(val).strip() if val else None

print("\n🚀 ===== TEST ŚRODOWISKA I KLUCZY ODDS =====\n")

# 1) Sprawdzenie Telegram
print("🔹 Telegram secrets:")
print("T_TOKEN =", "OK" if get_secret("T_TOKEN") else "❌ BRAK")
print("T_CHAT  =", "OK" if get_secret("T_CHAT") else "❌ BRAK")
print()

# 2) Sprawdzenie kluczy Odds
print("🔹 Klucze ODDS w Secrets:")
keys = []
for i in range(1, 11):
    name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
    val = get_secret(name)
    status = "OK" if val else "brak"
    print(f"{name}: {status}")
    if val:
        keys.append(val)

print(f"\n➡️ Liczba znalezionych kluczy: {len(keys)}\n")

if not keys:
    print("❌ BŁĄD: Nie wykryto żadnych kluczy Odds API!")
    print("Musisz je dodać do Secrets albo do .env")
    exit()

# 3) Test jednego zapytania do API
TEST_LEAGUE = "icehockey_nhl"
print(f"🔹 Test pojedynczego zapytania do ligi: {TEST_LEAGUE}")

test_url = f"https://api.the-odds-api.com/v4/sports/{TEST_LEAGUE}/odds/"

params = {
    "apiKey": keys[0],
    "regions": "eu",
    "markets": "h2h"
}

r = requests.get(test_url, params=params, timeout=15)

print("STATUS API:", r.status_code)
print("URL:", r.url)

if r.status_code == 200:
    data = r.json()
    print(f"✅ Liczba meczów z API: {len(data)}")

    if data:
        first = data[0]
        print("\n📌 Przykładowy mecz:")
        print(first["home_team"], "vs", first["away_team"])

        print("\nDostępne rynki w pierwszym meczu:")
        for b in first.get("bookmakers", []):
            print("Book:", b["key"])
            for m in b.get("markets", []):
                print("  -", m["key"])
else:
    print("❌ API NIE DZIAŁA – możliwe przyczyny:")
    print("- zły klucz")
    print("- przekroczony limit")
    print("- blokada konta")

print("\n✅ KONIEC TESTU\n")