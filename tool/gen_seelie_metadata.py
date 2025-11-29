#!/usr/bin/env python3

import json
from glob import glob


def generate_test_data():
    with open("metadata/MaterialExcelConfigData_idmap_gen.json", "rt", encoding="utf-8") as f:
        material_id_map = json.load(f)
    materials = {name: int(item_id) for item_id, name in material_id_map.items()}
    result = {
        "format": "GOOD",
        "version": 3,
        "source": "https://github.com/Patrick-Ze/AyakaSync",
        "materials": materials,
    }
    out_file = "gen-for-seelie-import.json"
    with open(out_file, 'wt', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    print(f"{out_file} generated")


def scan_seelie_exported_to_metadata():
    with open("metadata/MaterialExcelConfigData_idmap_gen.json", "rt", encoding="utf-8") as f:
        material_id_map = json.load(f)
    name2ids = {}
    for id_, name in material_id_map.items():
        name2ids.setdefault(name, []).append(int(id_))
    dup_name_items = {k:v for k,v in name2ids.items() if len(v) > 1}
    id_map_to_dups = {}
    for id_ls in dup_name_items.values():
        for i in id_ls:
            id_map_to_dups[i] = id_ls

    exported_files = glob("**/*-seelie-inventory.json", recursive=True)
    count = len(exported_files)
    assert count == 1, f"Expect only 1 exported file but exist {count}:\n" + "\n".join(exported_files)

    with open(exported_files[0], 'rt', encoding='utf-8') as f:
        seelie_data = json.load(f)
    metadata = {}
    for item in seelie_data['inventory']:
        item_id = item.pop('value')
        duplicates = id_map_to_dups.pop(item_id, None)
        if duplicates is None:
            metadata[item_id] = item
        else:
            for id_ in duplicates:
                metadata[id_] = item

    out_file = 'metadata/seelie_inventory_map.json'
    with open(out_file, 'wt', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"{out_file} generated")


if __name__ == "__main__":
    import os
    fullpath = os.path.abspath(__file__)
    workspace = os.path.dirname(os.path.dirname(fullpath))
    os.chdir(workspace)

    print('1. Generate test data for seelie inventory import')
    print('2. Generate metadata from seelie exported inventory')
    opt = input()
    if opt == '1':
        generate_test_data()
    elif opt == '2':
        scan_seelie_exported_to_metadata()
    else:
        print("Invalid input")

