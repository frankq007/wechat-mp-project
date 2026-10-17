#!/usr/bin/env python3
"""newspic (图片消息) 草稿创建全链路实测
流程: access_token -> 素材库取一张永久图片 media_id -> draft/add(article_type=newspic) -> draft/batchget 验证 -> draft/delete 清理
"""
import json
import os
import sys
import requests

APP_ID = os.environ.get("WECHAT_APP_ID", "")
APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")
if not APP_ID or not APP_SECRET:
    print("FATAL: 环境变量 WECHAT_APP_ID / WECHAT_APP_SECRET 缺失")
    sys.exit(1)

BASE = "https://api.weixin.qq.com/cgi-bin"


def api_get(url):
    r = requests.get(url, timeout=15)
    return r.json()


def api_post(url, payload):
    r = requests.post(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, timeout=30)
    return r.json()


def step(name):
    print(f"\n=== {name} ===")


# 1. access_token
step("1. 获取 access_token")
tok = api_get(f"{BASE}/token?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}")
if "access_token" not in tok:
    print("FATAL:", tok)
    sys.exit(1)
token = tok["access_token"]
print("ok, expires_in =", tok.get("expires_in"))

# 2. 从永久素材库取第一张图片的 media_id（不新增素材）
step("2. 素材库取一张已有永久图片 media_id")
mat = api_post(f"{BASE}/material/batchget_material?access_token={token}",
               {"type": "image", "offset": 0, "count": 1})
items = mat.get("item", [])
if not items:
    print("FATAL: 素材库没有图片:", json.dumps(mat, ensure_ascii=False)[:300])
    sys.exit(1)
img = items[0]
media_id = img["media_id"]
print("取到图片:", img.get("name"), "| media_id:", media_id[:20] + "...")

# 3. draft/add 创建 newspic 草稿
step("3. draft/add 创建 newspic 草稿")
draft = api_post(f"{BASE}/draft/add?access_token={token}", {
    "articles": [{
        "article_type": "newspic",
        "title": "newspic测试-图片消息",
        "author": "小马",
        "content": "这是一张图片消息测试。",
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
        "image_info": {
            "image_list": [{"image_media_id": media_id}]
        }
    }]
})
if "media_id" not in draft:
    print("FATAL: draft/add 失败:", json.dumps(draft, ensure_ascii=False))
    sys.exit(1)
draft_media_id = draft["media_id"]
print("OK 草稿已创建, media_id =", draft_media_id)

# 4. 验证：draft/batchget 看 article_type 是否为 newspic
step("4. draft/batchget 验证")
g = api_post(f"{BASE}/draft/batchget?access_token={token}",
             {"offset": 0, "count": 5, "no_content": 1})
found = None
for it in g.get("item", []):
    if it.get("media_id") == draft_media_id:
        found = it
        break
if found:
    ni = found["content"]["news_item"][0]
    print("验证 OK: article_type =", ni.get("article_type"),
          "| title =", ni.get("title"),
          "| media_id =", found["media_id"])
else:
    print("WARN: 前 5 条草稿里没找到新草稿（可能不在首页），再翻页找")
    for off in range(5, 50, 20):
        g = api_post(f"{BASE}/draft/batchget?access_token={token}",
                     {"offset": off, "count": 20, "no_content": 1})
        for it in g.get("item", []):
            if it.get("media_id") == draft_media_id:
                found = it
                break
        if found:
            break
    if found:
        ni = found["content"]["news_item"][0]
        print("验证 OK(翻页): article_type =", ni.get("article_type"),
              "| title =", ni.get("title"))
    else:
        print("WARN: 列表没找到, 尝试 draft/get 单查")
        dg = api_post(f"{BASE}/draft/get?access_token={token}", {"media_id": draft_media_id})
        if "news_item" in dg:
            ni = dg["news_item"][0]
            print("验证 OK(draft/get): article_type =", ni.get("article_type"), "| title =", ni.get("title"))
        else:
            print("FATAL: 单查也失败:", json.dumps(dg, ensure_ascii=False)[:300])

# 5. 清理测试草稿
step("5. 删除测试草稿(清理)")
del_resp = api_post(f"{BASE}/draft/delete?access_token={token}", {"media_id": draft_media_id})
print("删除结果:", del_resp)
print("\nDONE")