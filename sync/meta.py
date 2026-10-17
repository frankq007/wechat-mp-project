#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 articles/*.md，提取元数据并写入 SQLite（正文不进库）。

元数据提取规则（从 md 源稿解析）：
  - title    : 第一个 `# ` 标题（若文件名更友好可选，默认取首标题）
  - summary  : 首标题后的第一个非空段落（前 120 字）
  - theme    : YAML frontmatter 的 theme，缺省 claude-scroll
  - tags     : YAML frontmatter 的 tags，逗号分隔
  - author   : YAML frontmatter 的 author，缺省 小河
  - status   : 缺省 本地稿
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    from . import db
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sync import db

ARTICLES_DIR = Path(__file__).resolve().parent.parent / "articles"


def parse_frontmatter(text: str) -> dict:
    """解析可选的 YAML frontmatter（--- ... ---）。"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip().lower()] = val.strip().strip("'\"")
    return meta


def extract_metadata(md_path: Path) -> dict:
    """从单个 md 文件提取元数据。"""
    text = md_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    # 去掉 frontmatter 再取首个标题
    body = re.sub(r"^---\s*\n.*?\n---\s*\n", "", text, flags=re.S)
    title = fm.get("title") or (re.search(r"^#\s+(.+)$", body, re.M)
                                and re.search(r"^#\s+(.+)$", body, re.M).group(1).strip()) or md_path.stem
    # 摘要：首标题后第一个非空段落
    summary = fm.get("summary", "")
    if not summary:
        m = re.search(r"^#\s+.+?\n\n(.+?)\n", body, re.M | re.S)
        if m:
            summary = m.group(1).strip()
    if summary:
        summary = re.sub(r"\s+", " ", summary)[:120]
    return {
        "title": title,
        "summary": summary,
        "theme": fm.get("theme", "claude-scroll"),
        "tags": fm.get("tags", ""),
        "author": fm.get("author", "小河"),
        "src_path": str(md_path),
    }


def index_articles(conn, dir_path: Path | None = None) -> int:
    """扫描目录下所有 .md，写入元数据。返回处理的文件数。"""
    target = dir_path or ARTICLES_DIR
    n = 0
    if not target.exists():
        target.mkdir(parents=True, exist_ok=True)
    for md in sorted(target.glob("*.md")):
        if md.name.startswith((".", "_")):
            continue
        meta = extract_metadata(md)
        db.upsert_article(conn, **meta)
        n += 1
    return n