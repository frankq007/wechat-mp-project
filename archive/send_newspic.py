#!/usr/bin/env python3
"""发一张图片消息(newspic)：本地图 -> 永久素材 -> newspic 草稿 -> 验证"""
import json
import os
import sys
import requests

IMG_SRC = ""  # 用法: python3 send_newspic.py <图片路径> [标题]
TITLE = "newspic测试"
import argparse
import sys as _sys
_ap = argparse.ArgumentParser()
_ap.add_argument("image"); _ap.add_argument("-t","--title",default=TITLE)
_av = _ap.parse_args()
IMG_SRC, TITLE = _av.image, _av.title

APP_ID = os.environ.get("WECHAT_APP_ID", "")
APP_SECRET = os.environ.get("WECHAT_APP_SECRET", "")
if not APP_ID or not APP_SECRET:
    print("FATAL: 缺环境变量"); sys.exit(1)
BASE = "https://api.weixin.qq.com/cgi-bin"


def post_json(url, payload):
    r = requests.post(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, timeout=30)
    return r.json()


def step(name):
    print(f"\n=== {name} ===")


step("1. 转 RGB 临时副本")
import shutil, tempfile
tmp = tempfile.mktemp(suffix=".png")
from PIL import Image
im = Image.open(IMG_SRC).convert("RGB")
im.save(tmp)
print("ok ->", tmp, im.size)

step("2. access_token")
tok = requests.get(f"{BASE}/token?grant_type=client_credential&appid={APP_ID}&secret={APP_SECRET}", timeout=15).json()
if "access_token" not in tok:
    print("FATAL:", tok); sys.exit(1)
token = tok["access_token"]
print("ok")

step("3. 上传永久素材 material/add_material type=image")
r = requests.post(
    f"{BASE}/material/add_material?access_token={token}&type=image",
    files={"media": ("clip.png", open(tmp, "rb"), "image/png")}, timeout=60)
data = r.json()
if "media_id" not in data:
    print("FATAL:", data); sys.exit(1)
media_id = data["media_id"]
print("media_id =", media_id)

step("4. draft/add 建 newspic 草稿")
draft = post_json(f"{BASE}/draft/add?access_token={token}", {
    "articles": [{
        "article_type": "newspic",
        "title": TITLE,
        "content": "测试图片消息",
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
        "image_info": {"image_list": [{"image_media_id": media_id}]}
    }]
})
if "media_id" not in draft:
    print("FATAL:", draft); sys.exit(1)
draft_id = draft["media_id"]
print("草稿 media_id =", draft_id)

step("5. draft/get 验证")
g = post_json(f"{BASE}/draft/get?access_token={token}", {"media_id": draft_id})
if "news_item" in g:
    ni = g["news_item"][0]
    print("article_type =", ni.get("article_type"))
    print("title =", ni.get("title"))
    print("content =", ni.get("content"))
else:
    print("FATAL:", g)

step("6. 清理临时文件")
os.remove(tmp)
print("DONE")
print("\n草稿已保留在草稿箱(未删), media_id =", draft_id)