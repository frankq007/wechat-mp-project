#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""微信官方 API 封装：取 token、拉草稿箱、拉已发布。

凭据复用现成 xiaohu-wechat-format 的 config.json（app_id / app_secret），
与 publish.py / newspic.py 共用同一套，避免重复配置。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

SKILL_DIR = Path("/mnt/d/code/wx/xiaohu-wechat-format")
BASE = "https://api.weixin.qq.com/cgi-bin"


def load_config() -> dict:
    cfg_path = SKILL_DIR / "config.json"
    if not cfg_path.exists():
        print(f"错误: 找不到现成 skill 的 config.json: {cfg_path}")
        sys.exit(1)
    return json.load(open(cfg_path, encoding="utf-8"))


def resolve_credential(value, env_name: str) -> str:
    """凭据解析：环境变量优先，其次展开 config.json 里的 $VAR 占位。

    config.json 的 app_secret 写的是 "$WECHAT_APP_SECRET"（不落明文密钥），
    真值取自环境变量。与 publish.py / newspic.py 共用同一套解析顺序。
    """
    env_val = os.environ.get(env_name, "").strip()
    if env_val:
        return env_val
    if not value:
        return ""
    val = str(value).strip()
    expanded = os.path.expandvars(val)
    if expanded != val and not expanded.startswith("$"):
        return expanded.strip()
    return ""


def get_credentials() -> tuple[str, str]:
    """返回 (app_id, app_secret)；取不到则报错退出。"""
    wechat = load_config().get("wechat", {})
    app_id = resolve_credential(wechat.get("app_id"), "WECHAT_APP_ID")
    app_secret = resolve_credential(wechat.get("app_secret"), "WECHAT_APP_SECRET")
    if not app_id or not app_secret:
        print("错误: 未取到微信凭据。请设置环境变量 WECHAT_APP_ID / WECHAT_APP_SECRET，"
              "或在 xiaohu-wechat-format/config.json 的 wechat.app_secret 写 \"$WECHAT_APP_SECRET\"")
        sys.exit(1)
    return app_id, app_secret


def get_access_token() -> str:
    """获取微信 access_token。"""
    app_id, app_secret = get_credentials()
    url = f"{BASE}/token?grant_type=client_credential&appid={app_id}&secret={app_secret}"
    data = requests.get(url, timeout=15).json()
    if "access_token" in data:
        return data["access_token"]
    errcode, errmsg = data.get("errcode", "?"), data.get("errmsg", "未知错误")
    print(f"错误: 获取 access_token 失败 (errcode={errcode}: {errmsg})")
    if errcode in (40001, 40125):
        print("  → AppSecret 无效，请检查环境变量 WECHAT_APP_SECRET")
    elif errcode == 40164:
        print("  → IP 不在白名单，请到公众号后台添加当前 IP")
    sys.exit(1)


def _post(url: str, payload: dict) -> dict:
    """POST JSON。显式 UTF-8 解码响应——微信不返 charset，
    requests.json() 会退化到 ISO-8859-1 导致中文标题乱码。
    """
    r = requests.post(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, timeout=30)
    return json.loads(r.content.decode("utf-8"))


def fetch_drafts(token: str, count: int = 20, offset: int = 0) -> list[dict]:
    """拉取草稿箱（draft/batchget）。返回 item 列表。"""
    data = _post(f"{BASE}/draft/batchget?access_token={token}",
                 {"offset": offset, "count": count, "no_content": 1})
    if "item" in data:
        return data.get("item", [])
    errcode = data.get("errcode", 0)
    if errcode:
        print(f"警告: 拉取草稿箱失败 (errcode={errcode}: {data.get('errmsg','')})")
    return []


def fetch_published(token: str, count: int = 20, offset: int = 0) -> tuple[list[dict], str | None]:
    """拉取已发布文章（freepublish/batchget）。

    返回 (item 列表, 错误说明)。注意：freepublish 需要公众号具备“发布能力”权限，
    个人订阅号通常未授权（errcode 48001），此时已发布列表无法从官方拉取。
    """
    data = _post(f"{BASE}/freepublish/batchget?access_token={token}",
                 {"offset": offset, "count": count, "no_content": 1})
    if "item" in data:
        return data.get("item", []), None
    errcode = data.get("errcode", 0)
    if errcode == 48001:
        return [], ("48001: 公众号未授权“发布能力”，官方 freepublish 接口不可用。"
                   "已发布文章无法自动拉取，需人工登记或升级认证。")
    if errcode:
        return [], f"{errcode}: {data.get('errmsg','')}"
    return [], None