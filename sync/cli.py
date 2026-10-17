#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""公众号数据同步 CLI：草稿箱/已发布 ↔ 本地 SQLite。

子命令：
  init            建库建表
  index-articles  扫描 articles/*.md 写入元数据
  pull            拉微信草稿箱+已发布 → sqlite 镜像（需要凭据）
  draft ls        草稿列表（--db 本地库 / 默认... 见说明）
  publish ls      已发布列表
  report          差异/漂移核对
  db              SQL 查询本地库

示例：
  python3 sync/cli.py init
  python3 sync/cli.py index-articles
  python3 sync/cli.py pull
  python3 sync/cli.py draft ls
  python3 sync/cli.py report
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

try:                      # 作为包导入：python3 -m sync.cli
    from . import db, meta, sync
    from . import api as wxapi
except ImportError:       # 作为脚本运行：python3 sync/cli.py
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sync import db, meta, sync
    from sync import api as wxapi


def _conn(args) -> sqlite3.Connection:
    return db.connect(Path(args.db) if args.db else None)


def cmd_init(args):
    db.init(Path(args.db) if args.db else None)
    print(f"✓ 数据库已初始化")


def cmd_index(args):
    conn = _conn(args)
    n = meta.index_articles(conn, Path(args.dir) if args.dir else None)
    print(f"✓ 已索引 {n} 篇文章的元数据")


def cmd_pull(args):
    conn = _conn(args)
    token = wxapi.get_access_token()
    res = sync.pull_all(conn, token, count=args.count)
    print(f"✓ 同步完成：草稿 {res['drafts']} 条，已发布 {res['published']} 条")
    if res.get("published_error"):
        print(f"⚠ 已发布拉取受限 — {res['published_error']}")
        print("  → 草稿箱同步不受影响；已发布文章需人工登记到 sync_items(wx_status='已发布')")


def cmd_draft_ls(args):
    conn = _conn(args)
    rows = db.list_sync_items(conn, wx_status="草稿")
    _print_items(rows, "草稿")


def cmd_publish_ls(args):
    conn = _conn(args)
    rows = db.list_sync_items(conn, wx_status="已发布")
    _print_items(rows, "已发布")


def _print_items(rows, label):
    if not rows:
        print(f"（空）没有{label}记录")
        return
    print(f"共 {len(rows)} 条{label}：")
    for r in rows:
        print(f"  [{r['article_type']}] {r['title']}"
              f" | media_id={r['media_id'][:16]}..."
              f" | {r['updated_time'] or r['pushed_at'] or ''}")


def cmd_report(args):
    conn = _conn(args)
    rows = sync.report(conn)
    if not rows:
        print("✓ 无差异，一切一致")
        return
    print(f"发现 {len(rows)} 处需关注：")
    for r in rows:
        print(f"  · {r['type']}: {r.get('title','')} "
              f"({r.get('src') or r.get('media_id','')})")


def cmd_mark_published(args):
    """人工登记已发布文章（freepublish 接口未授权时的兜底）。"""
    conn = _conn(args)
    db.upsert_sync_item(
        conn, media_id=args.media_id,
        article_type=args.type, title=args.title, wx_status="已发布",
        message_id=args.message_id,
        published_at=args.published_at or db.now())
    # 若提供 --src：关联本地稿并建映射，让 report 不再误报
    if args.src:
        src_path = Path(args.src).resolve()
        if src_path.exists():
            m = meta.extract_metadata(src_path)
            art_id = db.upsert_article(conn, **m)
            db.link_article(conn, art_id, args.media_id, remote_hash="published")
            conn.execute("UPDATE articles SET status='已发布' WHERE id=?", (art_id,))
            conn.commit()
            print(f"  ✓ 已关联本地稿: {m['title']} (article_id={art_id})")
        else:
            print(f"  ⚠ --src 文件不存在，跳过关联: {src_path}")
    print(f"✓ 已登记为已发布: {args.title} (media_id={args.media_id[:16]}...)")


def cmd_db(args):
    conn = _conn(args)
    cur = conn.execute(args.sql)
    rows = cur.fetchall()
    if not rows:
        print("（空结果）")
        return
    cols = [d[0] for d in cur.description]
    for row in rows:
        print(" | ".join(f"{c}={v}" for c, v in zip(cols, tuple(row))))


def make_parser():
    p = argparse.ArgumentParser(prog="wechat-mp-sync",
                                description="公众号数据同步 CLI")
    p.add_argument("--db", help="数据库路径（默认 data/wechat_mp.db）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    ia = sub.add_parser("index-articles")
    ia.add_argument("--dir", help="md 目录（默认 articles/）")

    pull = sub.add_parser("pull")
    pull.add_argument("--count", type=int, default=20, help="每批拉取条数")

    dl = sub.add_parser("draft"); dl_s = dl.add_subparsers(dest="sub", required=True)
    dl_s.add_parser("ls")

    pl = sub.add_parser("publish"); pl_s = pl.add_subparsers(dest="sub", required=True)
    pl_s.add_parser("ls")

    sub.add_parser("report")

    mp = sub.add_parser("mark-published",
                        help="人工登记已发布文章（freepublish 未授权时的兜底）")
    mp.add_argument("--media-id", required=True)
    mp.add_argument("--title", required=True)
    mp.add_argument("--type", choices=["news", "newspic"], default="news")
    mp.add_argument("--message-id")
    mp.add_argument("--src", help="关联的本地 md 源稿路径（存在则写入 article_sync 映射）")
    mp.add_argument("--published-at", help="发布时间，默认当前")

    dbp = sub.add_parser("db")
    dbp.add_argument("--sql", required=True)
    return p


def main():
    args = make_parser().parse_args()
    cmd_map = {
        "init": cmd_init,
        "index-articles": cmd_index,
        "pull": cmd_pull,
        "report": cmd_report,
        "mark-published": cmd_mark_published,
        "db": cmd_db,
    }
    if args.cmd in ("draft", "publish"):
        if args.sub == "ls":
            (cmd_draft_ls if args.cmd == "draft" else cmd_publish_ls)(args)
        return
    func = cmd_map.get(args.cmd)
    if func:
        func(args)


if __name__ == "__main__":
    main()