import requests
import os

T_TOKEN = os.getenv("T_TOKEN")
T_CHAT = os.getenv("T_CHAT")         # Kanał TYPY
T_CHAT_RESULTS = os.getenv("T_CHAT_RESULTS") # Kanał WYNIKI

def test_channels():
    # Test kanału WYNIKI
    r1 = requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                      json={"chat_id": T_CHAT_RESULTS, "text": "✅ Test Kanału WYNIKI - OK"})
    
    # Test kanału TYPY
    r2 = requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                      json={"chat_id": T_CHAT, "text": "🔥 Test Kanału TYPY - OK"})
    
    print(f"Wynik WYNIKI: {r1.status_code} ({r1.text})")
    print(f"Wynik TYPY: {r2.status_code} ({r2.text})")

if __name__ == "__main__":
    test_channels()
