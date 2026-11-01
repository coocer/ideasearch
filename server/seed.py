"""首次引导的种子导入。

全新克隆的库是空的：没有方向、没有数据源，采集会返回 0 篇。
从仓库自带的 config.toml 导入一份默认配置作为起点。
"""

from __future__ import annotations

import json

from ideasearch.config import load_config


def seed_defaults(conn) -> int:
    """仅在还没有任何方向时导入；已有用户配置则不动。返回导入的方向数。"""
    existing = conn.execute("select count(*) as c from topics").fetchone()["c"]
    if existing:
        return 0

    cfg = load_config()
    count = 0
    for topic in cfg.topics:
        conn.execute(
            "insert or ignore into topics(key, label, keywords, weight, enabled) values (?,?,?,?,1)",
            (topic.key, topic.label, json.dumps(topic.keywords, ensure_ascii=False), float(topic.weight)),
        )
        count += 1

    categories = list(cfg.arxiv.get("categories", []))
    if categories:
        conn.execute(
            "insert into sources(kind, name, url, config, weight, enabled) values ('arxiv','arXiv','',?,1,1)",
            (json.dumps({"categories": categories}, ensure_ascii=False),),
        )

    for feed in cfg.feeds:
        conn.execute(
            "insert into sources(kind, name, url, config, weight, enabled) values ('rss',?,?,?,?,1)",
            (feed.name, feed.url, json.dumps({"feed_kind": feed.kind}, ensure_ascii=False),
             float(feed.weight)),
        )

    conn.commit()
    return count
