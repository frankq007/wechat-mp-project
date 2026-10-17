#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""参数化图片消息(newspic)发布：本地图 -> 永久素材 -> newspic 草稿。

复用现成 xiaohu-wechat-format 的 config.json 里的 app_id / app_secret，
与 publish.py 使用同一套凭据，避免重复配置。

用法:
    # 默认（仅推送，标题取文件名）
    python3 newspic.py --image cover.png

    # 指定标题 + 推送
    python3 newspic.py --image cover.png --title "今日快讯"

    # 仅生成草稿到草稿箱（默认），可 --publish 跳过(微信群发需谨慎,默认不做)

依赖:
    pip3 install requests Pillow
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import requests

# 复用本项目内 skill 的 config.json（author 等）；凭据从环境变量解析
PROJECT = Path(__file__).resolve().parent.parent
SKILL_DIR = PROJECT / "skill" / "xiaohu-wechat-format"
CONFIG = json.load(open(SKILL_DIR / "config.json", encoding="utf-8"))
WECHAT = CONFIG.get("wechat", {})

AUTHOR = WECHAT.get("author", "小河")
BASE = "https://api.weixin.qq.com/cgi-bin"


def resolve_credential(value, env_name: str) -> str:
    """环境变量优先，其次展开 config.json 里的 $VAR 占位（与 sync/api.py 一致）。"""
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


def post_json(url, payload):
    """POST JSON to WeChat, ensure_ascii=False (avoid title length escaping)"""
    r = requests.post(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    return json.loads(r.content.decode("utf-8"))


def get_access_token():
    """获取微信 access_token"""
    app_id = resolve_credential(WECHAT.get("app_id"), "WECHAT_APP_ID")
    app_secret = resolve_credential(WECHAT.get("app_secret"), "WECHAT_APP_SECRET")
    if not app_id or not app_secret:
        print("错误: 未取到微信凭据。请设置环境变量 WECHAT_APP_ID / WECHAT_APP_SECRET")
        sys.exit(1)
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


def to_rgb_copy(path: Path) -> Path:
    """微信素材要求 RGB，转一个临时副本避免 CMA/色图模式问题"""
    from PIL import Image
    tmp = Path(tempfile.mktemp(suffix=path.suffix or ".png"))
    Image.open(path).convert("RGB").save(tmp)
    return tmp


def upload_permanent_image(token: str, image_path: Path) -> str:
    """上传图片为永久素材，返回 media_id"""
    url = f"{BASE}/material/add_material?access_token={token}&type=image"
    ext = image_path.suffix.lower()
    ctype = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".png": "image/png", ".gif": "image/gif"}.get(ext, "image/jpeg")
    with open(image_path, "rb") as f:
        data = requests.post(url, files={"media": (image_path.name, f, ctype)}, timeout=60).json()
    if "media_id" in data:
        return data["media_id"]
    print(f"错误: 上传素材失败 - {data}")
    sys.exit(1)


def create_newspic_draft(token: str, title: str, image_media_id: str) -> str:
    """创建 newspic(图片消息) 草稿，返回草稿 media_id"""
    payload = {
        "articles": [{
            "article_type": "newspic",
            "title": title,
            "author": AUTHOR,
            "content": "图片消息",
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
            "image_info": {"image_list": [{"image_media_id": image_media_id}]},
        }]
    }
    data = post_json(f"{BASE}/draft/add?access_token={token}", payload)
    if "media_id" in data:
        return data["media_id"]
    print(f"错误: 推送草稿箱失败 - {data}")
    sys.exit(1)


def verify_draft(token: str, draft_id: str):
    """draft/get 验证草稿"""
    g = post_json(f"{BASE}/draft/get?access_token={token}", {"media_id": draft_id})
    if "news_item" in g:
        ni = g["news_item"][0]
        return ni.get("article_type"), ni.get("title")
    return None, None


def main():
    ap = argparse.ArgumentParser(description="发布图片消息(newspic)到草稿箱")
    ap.add_argument("--image", "-i", required=True, help="图片路径（封面/图）")
    ap.add_argument("--title", "-t", help="标题（默认取文件名）")
    ap.add_argument("--dry-run", action="store_true", help="只打印流程，不推送")
    args = ap.parse_args()

    img = Path(args.image).resolve()
    if not img.exists():
        print(f"错误: 图片不存在 - {img}")
        sys.exit(1)

    title = args.title or re.sub(r"\.[^.]+$", "", img.name)

    print(f"=== 1. access_token ===")
    token = get_access_token()
    print("  ✓ token 获取成功")

    print(f"=== 2. 转 RGB 临时副本 ===")
    tmp = to_rgb_copy(img)
    print(f"  ✓ {img.name} -> {tmp.name}")

    print(f"=== 3. 上传永久素材 ===")
    media_id = upload_permanent_image(token, tmp)
    print(f"  ✓ media_id = {media_id[:20]}...")

    if args.dry_run:
        print(f"\n[dry-run] 跳过推送")
        os.remove(tmp)
        return

    print(f"=== 4. 创建 newspic 草稿 ===")
    draft_id = create_newspic_draft(token, title, media_id)
    print(f"  ✓ 草稿 media_id = {draft_id}")

    atype, t = verify_draft(token, draft_id)
    print(f"=== 5. 验证 ===")
    print(f"  article_type = {atype}, title = {t}")

    os.remove(tmp)
    print(f"\n✅ 已推送到草稿箱，草稿 media_id = {draft_id}")
    print(f"   → 可到公众号后台 → 草稿箱 查看/发布")


if __name__ == "__main__":
    main()