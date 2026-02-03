import json
import os

def fix_coupons():
    file_path = "coupons.json"
    if not os.path.exists(file_path):
        print("Nie znaleziono pliku coupons.json")
        return

    # Mapa zmian: "stara_nazwa": "nowa_nazwa"
    mapping = {
        "icehockey_finland_liiga": "icehockey_liiga",
        "icehockey_shl": "icehockey_sweden_hockey_league",
        "soccer_turkey_super_lig": "soccer_turkey_super_league",
        "soccer_belgium_first_division_a": "soccer_belgium_first_div",
        "soccer_scotland_premiership": "soccer_spl",
        "soccer_efl_championship": "soccer_efl_champ"
    }

    with open(file_path, "r", encoding="utf-8") as f:
        coupons = json.load(f)

    fixed_count = 0
    for c in coupons:
        old_sport = c.get("sport")
        if old_sport in mapping:
            c["sport"] = mapping[old_sport]
            fixed_count += 1
            print(f"✅ Naprawiono: {old_sport} -> {c['sport']}")

    if fixed_count > 0:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(coupons, f, indent=4)
        print(f"\nGotowe! Naprawiono {fixed_count} kuponów.")
    else:
        print("\nNie znaleziono starych nazw do naprawy.")

if __name__ == "__main__":
    fix_coupons()
