import time
import random
import string
import hashlib
from typing import Dict

import requests

import logging_setup
logger = logging_setup.get_logger('challenge')

def md5(text: str) -> str:
    """
    计算输入文本的 MD5 哈希值。

    :param text: 输入的文本字符串。
    :return: 输入文本的 MD5 哈希值，以十六进制字符串表示。
    """
    _md5 = hashlib.md5()
    _md5.update(text.encode())
    return _md5.hexdigest()


# 随机文本
def random_text(num: int) -> str:
    """
    生成指定长度的随机文本。

    :param num: 随机文本的长度。
    :return: 生成的随机文本。
    """
    return "".join(random.sample(string.ascii_lowercase + string.digits, num))


def timestamp() -> int:
    """
    获取当前时间戳。

    :return: 当前时间戳。
    """
    return int(time.time())


def get_ds(web: bool) -> str:
    """
    获取米游社的签名字符串，用于访问米游社API时的签名验证。

    :param web: 是否为网页端请求。如果为 True，则使用手机网页端的 salt；如果为 False，则使用移动端的 salt。
    :return: 返回一个字符串，格式为"时间戳,随机字符串,签名"。
    """
    n = "idMMaGYmVgPzh3wxmWudUXKUPGidO7GM"
    i = str(timestamp())
    r = random_text(6)
    c = md5(f"salt={n}&t={i}&r={r}")
    return f"{i},{r},{c}"


def get_stoken_cookie(config) -> str:
    """
    获取带stoken的cookie

    :return: 正确的stoken的cookie
    """
    cookie = f"stuid={config.config['account']['stuid']};stoken={config.config['account']['stoken']}"
    if config.config["account"]["stoken"].startswith("v2_"):
        if config.config["account"]["mid"]:
            cookie += f";mid={config.config['account']['mid']}"
        else:
            raise ValueError(f"cookie require mid parament")
    return cookie


default_headers = {
    "DS": get_ds(web=False),
    # "cookie": get_stoken_cookie(),
    "x-rpc-client_type": "2",
    "x-rpc-app_version": "2.93.1",
    "x-rpc-sys_version": "12",
    "x-rpc-channel": "miyousheluodi",
    # "x-rpc-device_id": config.config["device"]["id"],
    # "x-rpc-device_name": config.config["device"]["name"],
    # "x-rpc-device_model": config.config["device"]["model"],
    "x-rpc-h265_supported": "1",
    "Referer": "https://app.mihoyo.com",
    "x-rpc-verify_key": "bll8iq97cem8",
    "x-rpc-csm_source": "discussion",
    "Content-Type": "application/json; charset=UTF-8",
    "Host": "bbs-api.miyoushe.com",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "User-Agent": "okhttp/4.9.3",
}


def log_request(req: requests.models.Response):
    status = req.status_code
    url = req.url
    method = req.request.method
    time_taken = req.elapsed.total_seconds()
    log_msg = f"[{method}] {url}  Status: {status}, Time: {time_taken:.4f}s\n{req.text}"
    logger.debug(log_msg)


def get_pass_challenge(config: Dict):
    bbs_get_captcha = f"https://bbs-api.miyoushe.com/misc/api/createVerification?is_high=true"
    headers = default_headers.copy()
    headers["cookie"] = config["cookie"]
    headers["x-rpc-device_id"] = config["device"]["id"]
    headers["x-rpc-device_name"] = config["device"]["name"]
    headers["x-rpc-device_model"] = config["device"]["model"]
    if config["device"]["fp"] != "":
        headers["x-rpc-device_fp"] = config["device"]["fp"]
    r1 = requests.get(bbs_get_captcha, headers=headers)
    data = r1.json()
    log_request(r1)
    if data["retcode"] != 0:
        return None

    gt = data["data"]["gt"]
    challenge = data["data"]["challenge"]
    params = {"gt": gt, "challenge": challenge, "use_v3_model": True, "save_result": False}
    headers = {"accept": "application/json"}
    r2 = requests.get("http://127.0.0.1:9645/pass_nine", headers=headers, params=params)
    log_request(r2)
    r2.raise_for_status()
    solved_data = r2.json().get("data", {})
    if solved_data.get("result") != "success":
        return None
    validate = solved_data.get("validate")
    if validate is None:
        return None

    bbs_captcha_verify = "https://bbs-api.miyoushe.com/misc/api/verifyVerification"
    params = {"geetest_challenge": challenge, "geetest_seccode": validate + "|jordan", "geetest_validate": validate}
    check_req = requests.post(bbs_captcha_verify, headers=headers, json=params)
    log_request(check_req)
    check = check_req.json()
    if check["retcode"] != 0:
        return None

    return check["data"]["challenge"]
