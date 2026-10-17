#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite 存储层：文章元数据 + 微信侧同步镜像。

正文存 md 文件（articles/），本库只存元数据索引和微信侧状态镜像。
三张表：
  articles      本地稿元数据（title/summary/author/theme/tags/src_path/md_hash/status）
  sync_items    微信侧镜像（media_id 唯一 / message_id / article_type / wx_status / 时间）
  article_sync  本地稿 <-> 微信侧 映射 + 版本哈希 + 最后同步时间
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "wechat_mp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT,
    summary     TEXT,
    author      TEXT DEFAULT '小河',
    src_path    TEXT UNIQUE,          -- md 文件路径（正文真源）
    theme       TEXT,
    tags        TEXT,                 -- 逗号分隔
    md_hash     TEXT,                 -- 本地正文哈希（用于漂移检测）
    status      TEXT DEFAULT '本地稿', -- 本地稿 | 草稿 | 已发布 | 已删
    created_at  TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS sync_items (
    media_id      TEXT PRIMARY KEY,    -- 微信草稿/素材 media_id
    message_id    TEXT,                -- 发布后的 msg_data_id（已发布才有）
    article_type  TEXT,                -- news(图文) | newspic(图片消息)
    title         TEXT,
    wx_status     TEXT DEFAULT '草稿', -- 草稿 | 已发布 | 已删
    pushed_at     TEXT,
    published_at  TEXT,
    updated_time  TEXT                 -- 微信侧更新时间
);

CREATE TABLE IF NOT EXISTS article_sync (
    article_id  INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
    media_id    TEXT REFERENCES sync_items(media_id) ON DELETE CASCADE,
    sync_at     TEXT,
    local_hash  TEXT,
    remote_hash TEXT,
    UNIQUE(article_id, media_id)
);
"""


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    db = db_path or DB_PATH
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(db_path: Path | None = None) -> None:
    conn = connect(db_path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def file_md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# ── articles ─────────────────────────────────────────────────────────
def upsert_article(conn, src_path, title=None, summary=None, theme=None,
                   tags=None, author=None, md_hash=None, status=None):
    src_path = str(src_path)
    existing = conn.execute(
        "SELECT id FROM articles WHERE src_path=?", (src_path,)).fetchone()
    md_hash = md_hash or file_md5(src_path)
    ts = now()
    if existing:
        sets = ["updated_at=?", "md_hash=?"]
        vals = [ts, md_hash]
        if title is not None:
            sets.append("title=?"); vals.append(title)
        if summary is not None:
            sets.append("summary=?"); vals.append(summary)
        if theme is not None:
            sets.append("theme=?"); vals.append(theme)
        if tags is not None:
            sets.append("tags=?"); vals.append(tags)
        if author is not None:
            sets.append("author=?"); vals.append(author)
        if status is not None:
            sets.append("status=?"); vals.append(status)
        vals.append(existing["id"])
        conn.execute(f"UPDATE articles SET {', '.join(sets)} WHERE id=?",
                     vals)
        art_id = existing["id"]
    else:
        cur = conn.execute(
            "INSERT INTO articles(title,summary,author,src_path,theme,tags,"
            "md_hash,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (title or "", summary or "", author or "小河", src_path, theme or "",
             tags or "", md_hash, status or "本地稿", ts, ts))
        art_id = cur.lastrowid
    conn.commit()
    return art_id


def get_article_by_src(conn, src_path):
    return conn.execute("SELECT * FROM articles WHERE src_path=?",
                        (str(src_path),)).fetchone()


def list_articles(conn, status=None):
    if status:
        return conn.execute("SELECT * FROM articles WHERE status=? ORDER BY updated_at DESC",
                            (status,)).fetchall()
    return conn.execute("SELECT * FROM articles ORDER BY updated_at DESC").fetchall()


# ── sync_items ────────────────────────────────────────────────────────
def upsert_sync_item(conn, media_id, article_type, title, wx_status,
                     message_id=None, published_at=None, updated_time=None, pushed_at=None):
    ts = now()
    existing = conn.execute("SELECT media_id FROM sync_items WHERE media_id=?",
                            (media_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE sync_items SET article_type=?, title=?, wx_status=?, "
            "message_id=?, published_at=?, updated_time=?, pushed_at=? WHERE media_id=?",
            (article_type, title, wx_status, message_id, published_at,
             updated_time, pushed_at or ts, media_id))
    else:
        conn.execute(
            "INSERT INTO sync_items(media_id,article_type,title,wx_status,"
            "message_id,pushed_at,published_at,updated_time) VALUES(?,?,?,?,?,?,?,?)",
            (media_id, article_type, title, wx_status, message_id,
             pushed_at or ts, published_at, updated_time))
    conn.commit()
    return media_id


def list_sync_items(conn, wx_status=None):
    if wx_status:
        return conn.execute("SELECT * FROM sync_items WHERE wx_status=? "
                            "ORDER BY COALESCE(updated_time,pushed_at) DESC",
                            (wx_status,)).fetchall()
    return conn.execute("SELECT * FROM sync_items ORDER BY "
                        "COALESCE(updated_time,pushed_at) DESC").fetchall()


def link_article(conn, article_id, media_id, remote_hash=None):
    art = conn.execute("SELECT md_hash FROM articles WHERE id=?",
                       (article_id,)).fetchone()
    conn.execute(
        "INSERT OR REPLACE INTO article_sync(article_id,media_id,sync_at,"
        "local_hash,remote_hash) VALUES(?,?,?,?,?)",
        (article_id, media_id, now(),
         art["md_hash"] if art else "", remote_hash))
    # 确保 media_id 在 sync_items 中（若缺，补一条占位）
    if not conn.execute("SELECT 1 FROM sync_items WHERE media_id=?",
                        (media_id,)).fetchone():
        conn.execute(
            "INSERT OR IGNORE INTO sync_items(media_id,title,wx_status,article_type,pushed_at)"
            " VALUES(?,?,?,?,?)",
            (media_id, art["title"] if art else "", "草稿", "news", now()))
    conn.commit()