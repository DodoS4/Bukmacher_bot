import os
import requests

def test_keys():
    # Dynamiczne generowanie listy kluczy do sprawdzenia (1-10)
    print("🔍 ROZPOCZYNAM TEST 10 KLUCZY API...\n")
    print(f"{'NAZWA SEKRETU':<15} | {'STATUS':<10} | {'POZOSTAŁO'} | {'ZUŻYTO'}")
    print("-" * 65)

    for i in range(1, 11):
        # Obsługa nazw ODDS_KEY_1, ODDS_KEY_2 itd.
        name = f"ODDS_KEY_{i}"
        key = os.getenv(name)
        
        # Opcjonalna obsługa Twojego pierwszego klucza, jeśli nie ma numerka
        if i == 1 and not key:
            key = os.getenv("ODDS_KEY")
            name = "ODDS_KEY"

        if not key:
            print(f"{name:<15} | ⚪ BRAK      | ---         | ---")
            continue
        
        # Zapytanie o listę sportów (lekki endpoint do testu)
        url = "https://api.the-odds-api.com/v4/sports/"
        params = {"apiKey": key}
        
        try:
            resp = requests.get(url, params=params)
            
            # Pobieranie danych o limitach z nagłówków
            remaining = resp.headers.get('x-requests-remaining', '0')
            used = resp.headers.get('x-requests-used', '0')
            quota = resp.headers.get('x-requests-quota', '0')

            if resp.status_code == 200:
                print(f"{name:<15} | ✅ OK        | {remaining:<11} | {used}/{quota}")
            elif resp.status_code == 401:
                print(f"{name:<15} | ❌ BŁĄD      | Unauthorized (Zły klucz)")
            elif resp.status_code == 429:
                print(f"{name:<15} | ⚠️ LIMIT     | 0           | {used}/{quota} (FULL)")
            else:
                print(f"{name:<15} | ❓ STATUS {resp.status_code}")
                
        except Exception as e:
            print(f"{name:<15} | ❌ ERROR     | Błąd połączenia")

    print("\n💡 Wskazówka: Jeśli widzisz 'BRAK', sprawdź czy klucze są dodane do Secrets/Environment Variables.")

if __name__ == "__main__":
    test_keys()
