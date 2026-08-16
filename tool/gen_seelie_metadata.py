#!/usr/bin/env python3

import json
from glob import glob

SEELIE_MAP_FILE = "metadata/seelie_inventory_map.json"


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
    with open(out_file, "wt", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"{out_file} generated")


def scan_seelie_exported_to_metadata():
    with open("metadata/MaterialExcelConfigData_idmap_gen.json", "rt", encoding="utf-8") as f:
        material_id_map = json.load(f)
    name2ids = {}
    for id_, name in material_id_map.items():
        name2ids.setdefault(name, []).append(int(id_))
    dup_name_items = {k: v for k, v in name2ids.items() if len(v) > 1}
    id_map_to_dups = {}
    for id_ls in dup_name_items.values():
        for i in id_ls:
            id_map_to_dups[i] = id_ls

    exported_files = glob("**/*-seelie-inventory.json", recursive=True)
    count = len(exported_files)
    assert count == 1, f"Expect only 1 exported file but exist {count}:\n" + "\n".join(exported_files)

    with open(exported_files[0], "rt", encoding="utf-8") as f:
        seelie_data = json.load(f)
    metadata = {}
    for item in seelie_data["inventory"]:
        item_id = item.pop("value")
        duplicates = id_map_to_dups.pop(item_id, None)
        if duplicates is None:
            metadata[item_id] = item
        else:
            for id_ in duplicates:
                metadata[id_] = item

    metadata = {k: v for k, v in sorted(metadata.items(), key=lambda x: [int(x[0])])}
    with open(SEELIE_MAP_FILE, "wt", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"{SEELIE_MAP_FILE} generated")


def patch_unknown_items():
    with open("unknown-seelie-inventory.json", "rt", encoding="utf-8") as f:
        missing = json.load(f)
    missing_id = {i["id"]: i for i in missing}
    with open("index.json", "rt", encoding="utf-8") as f:
        seelie = json.load(f)

    patched = {}
    for name, data in seelie.items():
        if "ids" in data:
            for tier, id_ in enumerate(data["ids"]):
                if id_ not in missing_id:
                    continue
                d = {"type": data["type"], "item": name, "tier": tier}
                patched[id_] = d
        elif "id" in data:
            d = {"type": data["type"], "item": name, "tier": 0}
            patched[data["id"]] = d

    with open(SEELIE_MAP_FILE, "r+", encoding="utf-8") as f:
        metadata = json.load(f)
    metadata.update({str(k): v for k, v in patched.items()})
    metadata = {k: v for k, v in sorted(metadata.items(), key=lambda x: [int(x[0])])}
    with open(SEELIE_MAP_FILE, "wt", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    print(f"{SEELIE_MAP_FILE} generated")

    still_missing_ids = sorted(set(missing_id.keys()) - set(patched.keys()))
    if len(still_missing_ids) > 0:
        still_missing = [missing_id[i] for i in still_missing_ids]
        items = [f"{i['id']}: {i['name']}" for i in still_missing]
        print(f"Still missing {len(items)} items: " + ", ".join(items))


if __name__ == "__main__":
    import os

    fullpath = os.path.abspath(__file__)
    workspace = os.path.dirname(os.path.dirname(fullpath))
    os.chdir(workspace)

    print("1. Generate test data for seelie inventory import")
    print("2. Generate metadata from seelie exported inventory")
    print("3. Patch unknown items based on index.js")
    opt = input()
    if opt == "1":
        generate_test_data()
    elif opt == "2":
        scan_seelie_exported_to_metadata()
    elif opt == "3":
        # 1. 在Chrome控制台源代码界面，查找未知的id
        # 2. 在控制台执行形如index-6ec98737.js中的对象，比如 Vk = {...}，然后执行`copy(Vk)`后粘贴为index.json文件
        # 3. 运行此函数
        patch_unknown_items()
    else:
        print("Invalid input")
