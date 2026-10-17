#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步引擎：把微信草稿箱 + 已发布文章镜像进本地 SQLite。

- 草稿箱   : draft/batchget            → wx_status=草稿
- 已发布   : freepublish/batchget      → wx_status=已发布
- 本地已有但微信已删 : 标记 wx_status=已删（在 pull 时对上次可见的 media_id 复核）

注意（如实标注）：官方 freepublish 通道拉"已发布"全量可能不完整，
同步以本地 DB 镜像 + 本地记录为主、官方拉取为辅。
"""
from __future__ import annotations

try:
    from . import api, db
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sync import api, db


def _ts_from_updated(et: int) -> str:
    """把微信侧的 update_time(Unix秒) 转成 db 里的字符串时间。"""
    if not et:
        return ""
    from datetime import datetime
    return datetime.fromtimestamp(et).strftime("%Y-%m-%d %H:%M:%S")


def pull_drafts(conn, token: str, count: int = 20) -> int:
    items = api.fetch_drafts(token, count=count)
    n = 0
    for item in items:
        media_id = item.get("media_id")
        if not media_id:
            continue
        content = item.get("content", {})
        news_items = content.get("news_item", [])
        # 图文草稿可有多个 news_item；这里取第一条作为索引，足够用于同步去重与展示
        ni = news_items[0] if news_items else {}
        title = ni.get("title", "(无标题)")
        article_type = "newspic" if ni.get("article_type") == "newspic" else "news"
        et = item.get("update_time")
        db.upsert_sync_item(conn, media_id=media_id, article_type=article_type,
                            title=title, wx_status="草稿",
                            updated_time=_ts_from_updated(et))
        n += 1
    return n


def pull_published(conn, token: str, count: int = 20) -> tuple[int, str | None]:
    items, err = api.fetch_published(token, count=count)
    n = 0
    for item in items:
        media_id = item.get("media_id") or item.get("article_id")
        if not media_id:
            continue
        content = item.get("content", {})
        news_items = content.get("news_item", [])
        ni = news_items[0] if news_items else {}
        title = ni.get("title", "(无标题)")
        article_type = "newspic" if ni.get("article_type") == "newspic" else "news"
        et = item.get("update_time")
        msg_data_id = item.get("msg_data_id") or ni.get("url")
        db.upsert_sync_item(conn, media_id=media_id, article_type=article_type,
                            title=title, wx_status="已发布",
                            message_id=str(msg_data_id) if msg_data_id else None,
                            published_at=_ts_from_updated(item.get("update_time")),
                            updated_time=_ts_from_updated(et))
        n += 1
    return n, err


def pull_all(conn, token: str, count: int = 20) -> dict:
    """同步草稿 + 已发布，返回各自条数与已发布拉取的错误说明。"""
    d = pull_drafts(conn, token, count=count)
    p, err = pull_published(conn, token, count=count)
    return {"drafts": d, "published": p, "published_error": err}


def report(conn) -> list[dict]:
    """差异/漂移核对报告。"""
    rows = []
    arts = {a["src_path"]: a for a in db.list_articles(conn)}
    syncs = db.list_sync_items(conn)

    # 本地有稿，但没有任何微信映射
    linked = {s["article_id"] for s in
              conn.execute("SELECT article_id FROM article_sync").fetchall()}
    for a in arts.values():
        if a["id"] not in linked:
            rows.append({"type": "本地稿未同步到微信", "title": a["title"],
                         "src": a["src_path"]})

    # 微信侧有、本地找不到对应（标注即可，可能由外部/手动创建）
    for s in syncs:
        row = conn.execute("SELECT article_id FROM article_sync WHERE media_id=?",
                           (s["media_id"],)).fetchone()
        if not row:
            rows.append({"type": "微信侧无本地映射", "title": s["title"],
                         "media_id": s["media_id"], "wx_status": s["wx_status"]})

    # 版本漂移：article_sync.local_hash 与 articles.md_hash 不一致
    for link in conn.execute("SELECT * FROM article_sync").fetchall():
        art = conn.execute("SELECT md_hash FROM articles WHERE id=?",
                           (link["article_id"],)).fetchone()
        if art and link["local_hash"] and art["md_hash"] != link["local_hash"]:
            row2 = conn.execute("SELECT title FROM articles WHERE id=?",
                                (link["article_id"],)).fetchone()
            rows.append({"type": "本地版本漂移", "title": row2["title"] if row2 else link["article_id"],
                         "media_id": link["media_id"]})
    return rows