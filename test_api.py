import os
import requests

def test_keys():
    # Pobieranie kluczy z otoczenia (Secrets)
    keys = {
        "ODDS_KEY": os.getenv("ODDS_KEY"),
        "ODDS_KEY_2": os.getenv("ODDS_KEY_2"),
        "ODDS_KEY_3": os.getenv("ODDS_KEY_3"),
        "ODDS_KEY_4": os.getenv("ODDS_KEY_4"),
        "ODDS_KEY_5": os.getenv("ODDS_KEY_5")
    }

    print("🔍 ROZPOCZYNAM TEST KLUCZY API...\n")
    print(f"{'NAZWA SEKRETU':<15} | {'STATUS':<10} | {'POZOSTAŁO LIMITU'}")
    print("-" * 50)

    for name, key in keys.items():
        if not key:
            print(f"{name:<15} | ❌ BRAK     | Nie zdefiniowano w Secrets")
            continue
        
        # Zapytanie o status konta (najtańsze zapytanie)
        url = f"https://api.the-odds-api.com/v4/sports/?apiKey={key}"
        
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                # Pobieranie informacji o limicie z nagłówków API
                remaining = resp.headers.get('x-requests-remaining', 'Nieznane')
                used = resp.headers.get('x-requests-used', 'Nieznane')
                print(f"{name:<15} | ✅ OK       | {remaining} zapytania (Zużyto: {used})")
            elif resp.status_code == 401:
                print(f"{name:<15} | ❌ BŁĄD     | Nieprawidłowy klucz (Unauthorized)")
            elif resp.status_code == 429:
                print(f"{name:<15} | ⚠️ LIMIT    | Przekroczono limit zapytań")
            else:
                print(f"{name:<15} | ❓ STATUS {resp.status_code}")
        except Exception as e:
            print(f"{name:<15} | ❌ ERROR    | Problem z połączeniem: {e}")

if __name__ == "__main__":
    test_keys()
