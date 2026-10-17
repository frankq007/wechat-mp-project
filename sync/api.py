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

from scripts.cred import resolve_credential

SKILL_DIR = Path(__file__).resolve().parent.parent / "skill" / "xiaohu-wechat-format"
BASE = "https://api.weixin.qq.com/cgi-bin"


REQUIRED_KEYS = ("settings.default_theme", "wechat.author", "image_search_paths")


def load_config() -> dict:
    cfg_path = SKILL_DIR / "config.json"
    if not cfg_path.exists():
        print(f"错误: 找不到 skill 的 config.json: {cfg_path}")
        print("  clone 后请先: cp skill/xiaohu-wechat-format/config.example.json "
              "skill/xiaohu-wechat-format/config.json")
        sys.exit(1)
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    # L3 自检：关键字段存在性（缺少时提示而不是静默用默认值）
    missing = []
    for k in REQUIRED_KEYS:
        cur = cfg
        ok = True
        for part in k.split("."):
            if not isinstance(cur, dict) or part not in cur:
                ok = False
                break
            cur = cur[part]
        if not ok:
            missing.append(k)
    if missing:
        print(f"警告: config.json 缺少关键字段（将使用脚本默认值）: {missing}")
    return cfg


def get_credentials() -> tuple[str, str]:
    """返回 (app_id, app_secret)；取不到则报错退出。"""
    wechat = load_config().get("wechat", {})
    app_id, app_secret = resolve_credential(wechat.get("app_id"), "WECHAT_APP_ID"), \
                         resolve_credential(wechat.get("app_secret"), "WECHAT_APP_SECRET")
    if not app_id or not app_secret:
        print("错误: 未取到微信凭据。请设置环境变量 WECHAT_APP_ID / WECHAT_APP_SECRET，"
              "或在 skill/xiaohu-wechat-format/config.json 的 wechat.app_secret 写 \"$WECHAT_APP_SECRET\"")
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