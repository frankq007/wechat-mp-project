#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""极薄发布封装：统一调用现成 xiaohu-wechat-format skill，并自动登记进本地 SQLite。

两条发布线（均只到草稿箱，不群发）：
  news     图文消息 → xiaohu scripts/publish.py（md 排版 → 上传封面/正文图 → 草稿箱）
  newspic  图片消息 → 本项目 scripts/newspic.py（本地图 → 永久素材 → newspic 草稿）

发布成功后自动：索引 md 元数据 + 写 sync_items(草稿) + 建 article_sync 映射，
这样 data-sync 的 report 不会把本项目发出的稿子误判为"微信侧无本地映射"。

用法:
    # 图文
    python3 scripts/release.py news --input articles/xx.md --cover images/covers/xx.png
    python3 scripts/release.py news --input articles/xx.md --cover c.png --theme claude-scroll

    # 图片消息
    python3 scripts/release.py newspic --image images/covers/xx.png --title "标题"

    # 跳过本地登记
    python3 scripts/release.py news --input x.md --cover c.png --no-register
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
XIAOHU_PUBLISH = PROJECT / "skill" / "xiaohu-wechat-format" / "scripts" / "publish.py"
NEWSPIC = PROJECT / "scripts" / "newspic.py"

# publish.py 输出 "草稿 media_id: xxx"；newspic.py 输出 "草稿 media_id = xxx"
# 兼容 publish.py 的 "草稿 media_id: xxx" / newspic.py 的 "草稿 media_id = xxx"
MEDIA_ID_RE = re.compile(r"(?:草稿\s+)?media_id\s*[:=]\s*([A-Za-z0-9_-]{10,})")


def run(cmd: list[str]) -> str:
    """执行子进程，实时透传输出，返回 stdout 文本。"""
    print(f"$ {' '.join(str(c) for c in cmd)}\n")
    proc = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out, end="" if out.endswith("\n") else "\n")
    if proc.returncode != 0:
        print(f"\n✗ 发布失败（退出码 {proc.returncode}）")
        sys.exit(proc.returncode)
    return out


def extract_media_id(output: str) -> str | None:
    m = MEDIA_ID_RE.search(output)
    return m.group(1) if m else None


def register(md_path: Path | None, media_id: str, title: str, article_type: str):
    """把发布结果登记进本地 SQLite。"""
    sys.path.insert(0, str(PROJECT))
    from sync import db, meta

    conn = db.connect()
    db.init(PROJECT / "data" / "wechat_mp.db")
    db.upsert_sync_item(conn, media_id=media_id, article_type=article_type,
                        title=title, wx_status="草稿")
    if md_path and md_path.exists():
        m = meta.extract_metadata(md_path)
        art_id = db.upsert_article(conn, **m)
        db.link_article(conn, art_id, media_id)
        conn.execute("UPDATE articles SET status='草稿' WHERE id=?", (art_id,))
        conn.commit()
        print(f"✓ 已登记：article_id={art_id} ↔ media_id={media_id[:16]}...")
    else:
        print(f"✓ 已登记 sync_items：media_id={media_id[:16]}...")
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="公众号发布封装（只到草稿箱）")
    sub = ap.add_subparsers(dest="kind", required=True)

    news = sub.add_parser("news", help="图文消息")
    news.add_argument("--input", "-i", required=True, help="Markdown 源稿")
    news.add_argument("--cover", "-c", help="封面图路径")
    news.add_argument("--title", "-t", help="标题（默认从 md 提取）")
    news.add_argument("--theme", default=None, help="排版主题（默认 config 的 claude-scroll）")
    news.add_argument("--source-url", "-s", default="", help="原文链接")
    news.add_argument("--dry-run", action="store_true")
    news.add_argument("--no-register", action="store_true", help="不写入本地 DB")

    pic = sub.add_parser("newspic", help="图片消息")
    pic.add_argument("--image", "-i", required=True, help="图片路径")
    pic.add_argument("--title", "-t", help="标题（默认取文件名）")
    pic.add_argument("--md", help="可选：关联的本地 md 源稿路径")
    pic.add_argument("--dry-run", action="store_true")
    pic.add_argument("--no-register", action="store_true", help="不写入本地 DB")

    args = ap.parse_args()

    if args.kind == "news":
        if not XIAOHU_PUBLISH.exists():
            print(f"错误: 找不到现成排版发布脚本 {XIAOHU_PUBLISH}")
            sys.exit(1)
        md = Path(args.input).resolve()
        if not md.exists():
            print(f"错误: md 源稿不存在 - {md}")
            sys.exit(1)
        cmd = [sys.executable, XIAOHU_PUBLISH, "--input", md]
        if args.cover:
            cmd += ["--cover", Path(args.cover).resolve()]
        if args.title:
            cmd += ["--title", args.title]
        if args.theme:
            cmd += ["--theme", args.theme]
        if args.source_url:
            cmd += ["--source-url", args.source_url]
        if args.dry_run:
            cmd += ["--dry-run"]
        out = run(cmd)
        if args.dry_run or args.no_register:
            return
        media_id = extract_media_id(out)
        if not media_id:
            print("✗ 发布似乎成功但未能从输出解析 media_id，跳过本地登记。")
            print("  请检查上方输出是否含有 media_id/草稿 media_id；如确实发布成功，")
            print("  可稍后执行 sync/cli.py pull 补齐映射，或用 sync/cli.py db 查询。")
            sys.exit(3)
        title = args.title or _md_title(md)
        register(md, media_id, title, "news")

    else:  # newspic
        img = Path(args.image).resolve()
        if not img.exists():
            print(f"错误: 图片不存在 - {img}")
            sys.exit(1)
        cmd = [sys.executable, NEWSPIC, "--image", img]
        if args.title:
            cmd += ["--title", args.title]
        if args.dry_run:
            cmd += ["--dry-run"]
        out = run(cmd)
        if args.dry_run or args.no_register:
            return
        media_id = extract_media_id(out)
        if not media_id:
            print("⚠ 未能解析 media_id，跳过本地登记")
            return
        title = args.title or re.sub(r"\.[^.]+$", "", img.name)
        md = Path(args.md).resolve() if args.md else None
        register(md, media_id, title, "newspic")


def _md_title(md: Path) -> str:
    """从 md 提取标题：优先 frontmatter 的 title（铁律 9：正文不再写 H1）。"""
    sys.path.insert(0, str(PROJECT))
    from sync import meta
    try:
        return meta.extract_metadata(md)["title"]
    except Exception:
        return md.stem


if __name__ == "__main__":
    main()
