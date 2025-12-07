#!/usr/bin/env python3

import os
import json
import shutil
from glob import glob
from itertools import cycle, islice
from typing import Dict

import yaml
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


def get_path(path: str):
    cwd = os.path.dirname(os.path.abspath(__file__))
    abs_path = os.path.join(cwd, path)
    return abs_path


def init_delta_request(cfg: Dict):
    headers = {
        "Cookie": cfg["cookie"],
        "Content-Type": "application/json",
        "Referer": "https://webstatic.mihoyo.com",
        "User-Agent": cfg["ua"],
    }

    avatar_api = "https://api-takumi.mihoyo.com/event/e20200928calculate/v1/avatar/list"
    avatar_filter = {"page": 1, "size": 1000, "is_all": True}
    r1 = requests.post(avatar_api, json=avatar_filter, headers=headers)
    r1.raise_for_status()
    avatar_list = []
    avatar_data = r1.json()
    for d in avatar_data["data"]["list"]:
        skill_list = [i["group_id"] for i in d["skill_list"] if i["max_level"] > 1]
        # 跳过无技能信息的人偶和多元素的旅行者，避免后面请求计算器API时出错
        if len(skill_list) == 0 or d["name"] == "旅行者":
            continue
        d["skill_id_list"] = skill_list
        avatar_list.append(d)
    avatar_list.sort(key=lambda x: x["id"])

    weapon_api = "https://api-takumi.mihoyo.com/event/e20200928calculate/v1/weapon/list"
    weapon_filter = {"page": 1, "size": 1000, "weapon_levels": [1, 2, 3, 4, 5]}
    r2 = requests.post(weapon_api, json=weapon_filter, headers=headers)
    r2.raise_for_status()
    weapon_data = r2.json()
    weapon_list = sorted(weapon_data["data"]["list"], key=lambda x: x["id"])

    avatar_by_type = {}
    for avatar in avatar_list:
        wtype = avatar["weapon_cat_id"]
        avatar_by_type.setdefault(wtype, []).append(avatar)
    weapon_by_type = {}
    for weapon in weapon_list:
        wtype = weapon["weapon_cat_id"]
        weapon_by_type.setdefault(wtype, []).append(weapon)

    promotion_deltas = []
    for wtype, characters in avatar_by_type.items():
        weapons = weapon_by_type.get(wtype, [])
        max_len = max(len(weapons), len(characters))
        cycle_weapons = islice(cycle(weapons), max_len)
        cycle_characters = islice(cycle(characters), max_len)
        for char, weapon in zip(cycle_characters, cycle_weapons):
            delta = {
                "avatar_id": char["id"],
                "avatar_level_current": 1,
                "avatar_level_target": 90,
                "skill_list": [{"id": i, "level_current": 1, "level_target": 10} for i in char["skill_id_list"]],
                "weapon": {
                    "id": weapon["id"],
                    "level_current": 1,
                    "level_target": weapon["max_level"],
                },
            }
            promotion_deltas.append(delta)
    return promotion_deltas


def read_config_files():
    config_data = {}
    os.makedirs(get_path("config"), exist_ok=True)
    cfg_files = glob(get_path("config/*.yaml"))
    if len(cfg_files) == 0:
        default_file = get_path("config/config.yaml")
        shutil.copy(f"{default_file}.example", default_file)
        raise SystemExit(f"Invalid config file, please update `{default_file}`")
    for path in cfg_files:
        with open(path, "r+", encoding="utf-8") as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
            uid = data["games"]["cn"]["genshin"].get("uid")
            if not uid:
                params = {"game_biz": "hk4e_cn"}
                api_url = "https://api-takumi.mihoyo.com/binding/api/getUserGameRolesByCookie"
                headers = {
                    "Content-Type": "application/json",
                    "Cookie": data["account"]["cookie"],
                    "User-Agent": data["games"]["cn"]["useragent"],
                }
                r = requests.get(api_url, params=params, headers=headers)
                r.raise_for_status()
                d = r.json()
                assert d["retcode"] == 0, d["message"]
                match = next(i for i in d["data"]["list"] if i["game_biz"] == params["game_biz"])
                uid = match["game_uid"]
                data["games"]["cn"]["genshin"]["uid"] = uid

                f.seek(0)
                f.write(yaml.dump(data, Dumper=yaml.Dumper, sort_keys=False))
                f.truncate()
                f.flush()
            uid = str(uid)
            config_data[uid] = {"cookie": data["account"]["cookie"], "ua": data["games"]["cn"]["useragent"]}
    return config_data


def get_overall_consume(uid: str, region="cn_gf01"):
    global deltas
    cfg = uid_config_data[uid]
    if len(deltas) == 0:
        deltas = init_delta_request(cfg)
    payload = {"items": deltas, "region": region, "uid": uid}
    headers = {
        "Cookie": cfg["cookie"],
        "Content-Type": "application/json",
        "Referer": "https://webstatic.mihoyo.com",
        "User-Agent": cfg["ua"],
    }
    api_url = "https://api-takumi.mihoyo.com/event/e20200928calculate/v3/batch_compute"
    r = requests.post(api_url, json=payload, headers=headers)
    r.raise_for_status()
    data = r.json()
    if data.get("retcode") != 0:
        raise Exception(f"API Error {data.get('retcode')}: {data.get('message')}")

    # 提取背包数据
    overall_consume = data.get("data", {}).get("overall_consume", [])
    return overall_consume


GOOD_id_map = {}
seelie_metadata = {}
deltas = {}
uid_config_data = read_config_files()


# 初始化 FastAPI 应用
app = FastAPI()


class User(BaseModel):
    uid: str


@app.get("/inventory/raw/{uid}", summary="根据UID获取用户背包内容")
async def read_user(uid: str):
    if uid not in uid_config_data:
        raise HTTPException(status_code=404, detail=f"User with uid {uid} not found in the known list")
    inventories = get_overall_consume(uid)
    return inventories


@app.get("/inventory/good/{uid}", summary="根据UID获取用户背包内容 (返回GOOD格式)")
async def read_inventory_as_good_format(uid: str):
    global GOOD_id_map
    if uid not in uid_config_data:
        raise HTTPException(status_code=404, detail=f"User with uid {uid} not found in the known list")
    overall_consume = get_overall_consume(uid)

    inventory = []
    for item in overall_consume:
        total_num = item["num"]
        lack_num = item["lack_num"]
        actual_count = total_num - lack_num  # 实际拥有数量
        if actual_count > 0:
            inventory.append({"id": item["id"], "count": actual_count, "accurate": lack_num != 0})
    inventory.append({"id": 113021, "count": 999, "accurate": False})

    if len(GOOD_id_map) == 0:
        with open(get_path("metadata/MaterialExcelConfigData_idmap_gen.json"), "rt", encoding="utf-8") as f:
            GOOD_id_map = json.load(f)
            GOOD_id_map = {int(k): v for k, v in GOOD_id_map.items()}
    materials = {GOOD_id_map[i["id"]]: i["count"] for i in inventory}
    result = {
        "format": "GOOD",
        "version": 3,
        "source": "https://github.com/Patrick-Ze/AyakaSync",
        "materials": materials,
    }
    return result


@app.get("/inventory/seelie/{uid}", summary="根据UID获取用户背包内容 (返回seelie格式)")
async def read_inventory_as_seelie_format(uid: str):
    global seelie_metadata
    if len(seelie_metadata) == 0:
        with open(get_path("metadata/seelie_inventory_map.json"), "rt", encoding="utf-8") as f:
            load_data = json.load(f)
        seelie_metadata = {int(k): v for k, v in load_data.items()}

    if uid not in uid_config_data:
        raise HTTPException(status_code=404, detail=f"User with uid {uid} not found in the known list")
    overall_consume = get_overall_consume(uid)

    inventory = []
    for item in overall_consume:
        total_num = item["num"]
        lack_num = item["lack_num"]
        actual_count = total_num - lack_num  # 实际拥有数量
        if actual_count > 0:
            item_data = seelie_metadata[item['id']].copy()
            item_data['value'] = actual_count
            inventory.append(item_data)
    # 养成计算器不返回异梦溶媒的数量，固定其数值以便seelie规划使用
    inventory.append({"type": "special", "item": "dream_solvent", "tier": 0, "value": 999})

    result = {"inventory": inventory}
    return result


if __name__ == "__main__":
    cwd = os.path.dirname(os.path.abspath(__file__))
    os.chdir(cwd)

    import uvicorn
    filename = os.path.splitext(os.path.basename(__file__))[0]
    uvicorn.run(
        f"{filename}:app",
        port=20928,
        host="0.0.0.0",
        reload=True,
    )
