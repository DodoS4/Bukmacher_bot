import os
import requests

def get_secret(name):
    val = os.environ.get(name) or os.getenv(name)
    return str(val).strip() if val else None

def check_everything():
    print("=== START DIAGNOSTYKI API ===")
    
    # 1. Sprawdzanie zużycia kluczy
    for i in range(1, 11):
        name = "ODDS_KEY" if i == 1 else f"ODDS_KEY_{i}"
        key = get_secret(name)
        if not key: continue
        
        url = "https://api.the-odds-api.com/v4/sports"
        try:
            r = requests.get(url, params={"apiKey": key}, timeout=10)
            rem = r.headers.get('x-requests-remaining', '0')
            if r.status_code == 200:
                print(f"✅ {name}: OK (Pozostało: {rem})")
            else:
                print(f"❌ {name}: Błąd {r.status_code} ({r.text[:50]})")
        except:
            print(f"💥 {name}: Błąd połączenia")

    print("\n=== LISTA DOSTĘPNYCH LIG ===")
    # 2. Pobieranie nazw lig (z pierwszego działającego klucza)
    api_key = get_secret("ODDS_KEY") or get_secret("ODDS_KEY_1")
    if api_key:
        try:
            resp = requests.get("https://api.the-odds-api.com/v4/sports", params={"apiKey": api_key})
            if resp.status_code == 200:
                for l in resp.json():
                    if any(x in l['key'] for x in ["soccer", "icehockey"]):
                        print(f"KEY: {l['key']} | TITLE: {l['title']}")
        except: pass

if __name__ == "__main__":
    check_everything()
