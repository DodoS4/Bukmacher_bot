import json
import os

def fix_coupons():
    file_path = "coupons.json"
    if not os.path.exists(file_path):
        print("❌ Nie znaleziono pliku coupons.json")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        coupons = json.load(f)

    print(f"📊 Znaleziono {len(coupons)} kuponów.")
    
    # Mapa zmian - dopasowana do tego, co najczęściej generuje błędy
    mapping = {
        "icehockey_finland_liiga": "icehockey_liiga",
        "icehockey_shl": "icehockey_sweden_hockey_league",
        "icehockey_sweden_shl": "icehockey_sweden_hockey_league",
        "soccer_turkey_super_lig": "soccer_turkey_super_league",
        "soccer_belgium_first_division_a": "soccer_belgium_first_div",
        "soccer_scotland_premiership": "soccer_spl",
        "soccer_efl_championship": "soccer_efl_champ",
        "icehockey_germany_del": "icehockey_del", # na wypadek zmiany w API
        "icehockey_switzerland_nla": "icehockey_switzerland_national_league" # przykład
    }

    fixed_count = 0
    print("\n🔎 Aktualne ligi w kuponach:")
    for c in coupons:
        old_sport = c.get("sport")
        print(f"- {old_sport}") # To pokaże Ci w logach, co tam naprawdę jest
        
        if old_sport in mapping:
            c["sport"] = mapping[old_sport]
            fixed_count += 1
            print(f"  ✅ ZMIANA NA: {c['sport']}")

    if fixed_count > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(coupons, f, indent=4)
        print(f"\n🚀 Sukces! Naprawiono {fixed_count} pozycji.")
    else:
        print("\nℹ️ Nie dopasowano żadnej nazwy z mapy zmian. Sprawdź pisownię w logach powyżej.")

if __name__ == "__main__":
    fix_coupons()
