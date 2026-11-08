#!/usr/bin/env python3

import json
import time
from glob import glob
from html.parser import HTMLParser

import requests

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

    exported_files = glob("**/*account*-seelie-inventory.json", recursive=True)
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


def extract_js_files(html_content: str) -> list[str]:
    js_files = []

    # 定义子类来复用 HTMLParser 的回调机制
    class Parser(HTMLParser):
        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            # 1. 匹配 <script> 标签中的 src 属性
            if tag == "script" and "src" in attrs_dict:
                js_files.append(attrs_dict["src"])
            # 2. 匹配 <link> 标签中以 .js 结尾的链接（如 modulepreload）
            elif tag == "link" and "href" in attrs_dict:
                href = attrs_dict["href"]
                if href.split("?")[0].endswith(".js"):
                    js_files.append(href)

    Parser().feed(html_content)
    return js_files


def patch_unknown_items():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
    }
    r1 = requests.get("https://seelie.me/", headers=headers)
    js_files = extract_js_files(r1.text)
    index_js = next(i for i in js_files if "/index-" in i)
    r2 = requests.get(f"https://seelie.me/{index_js}", headers=headers)
    start = r2.text.find("={horn:") + 1
    end = r2.text.find("}}", start) + 2
    content = r2.text[start:end]
    out_file = "index.json"
    with open(out_file, "wt", encoding="utf-8") as f:
        f.write(f"ayaka={content}; copy(ayaka); console.log(`Please paste to file`);")

    print("Please run code of 'index.json' in Chrome console then pase to overwrite the file")
    mtime = os.stat(out_file).st_mtime
    while True:
        if os.stat(out_file).st_mtime != mtime:
            try:
                with open(out_file, "rt", encoding="utf-8") as f:
                    seelie = json.load(f)
                break
            except:
                pass
        time.sleep(0.2)

    patched = {}
    for name, data in seelie.items():
        if "ids" in data:
            for tier, id_ in enumerate(data["ids"]):
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

    # still_missing_ids = sorted(set(missing_id.keys()) - set(patched.keys()))
    # if len(still_missing_ids) > 0:
    #     still_missing = [missing_id[i] for i in still_missing_ids]
    #     items = [f"{i['id']}: {i['name']}" for i in still_missing]
    #     print(f"Still missing {len(items)} items: " + ", ".join(items))


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
        patch_unknown_items()
    else:
        print("Invalid input")
