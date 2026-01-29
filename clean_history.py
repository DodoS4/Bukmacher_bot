import json

def remove_nba():
    file_name = 'history.json'
    
    try:
        # 1. Wczytaj dane
        with open(file_name, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        original_count = len(history)
        
        # 2. Przefiltruj - zostaw tylko to, co NIE jest NBA
        # Szukamy słowa 'nba' w polu 'sport' (małe/duże litery nie grają roli)
        clean_history = [
            bet for bet in history 
            if 'nba' not in str(bet.get('sport', '')).lower()
        ]
        
        removed_count = original_count - len(clean_history)
        
        # 3. Zapisz poprawiony plik
        with open(file_name, 'w', encoding='utf-8') as f:
            json.dump(clean_history, f, indent=4, ensure_ascii=False)
            
        print(f"✅ Gotowe! Usunięto {removed_count} rekordów NBA.")
        print(f"📄 Pozostało meczów w historii: {len(clean_history)}")
        
    except FileNotFoundError:
        print("❌ Błąd: Nie znaleziono pliku history.json")
    except Exception as e:
        print(f"❌ Wystąpił błąd: {e}")

if __name__ == "__main__":
    remove_nba()
