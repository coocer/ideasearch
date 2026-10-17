"""排序与筛选：去重 → 方向归属 → 打分 → 取 TopN。

打分 = 主题关键词命中(标题权重高) + 顶会录用 + 时效 + 来源权重。
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from .config import Config, Topic

_NORM = re.compile(r"[^a-z0-9\u4e00-\u9fff ]+")
_WS = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WS.sub(" ", _NORM.sub(" ", (text or "").lower())).strip()


def dedupe(items: list[dict]) -> list[dict]:
    """按标题归一化去重，保留信息量更大（摘要更长）的一条。"""
    best: dict[str, dict] = {}
    for item in items:
        key = _normalize(item.get("title", ""))[:120]
        if not key:
            continue
        current = best.get(key)
        if current is None or len(item.get("abstract", "")) > len(current.get("abstract", "")):
            best[key] = item
    return list(best.values())


def _days_old(published: str) -> float:
    try:
        day = datetime.strptime(published[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 30.0
    return max((datetime.now(timezone.utc) - day).total_seconds() / 86400, 0.0)


def assign_topic(item: dict, topics: list[Topic]) -> tuple[str, int]:
    """返回 (最匹配方向 key, 命中次数)。未命中任何方向则归到第一项。"""
    title = (item.get("title") or "").lower()
    body = f"{title} {(item.get('abstract') or '').lower()}"
    best_key, best_hits = (topics[0].key if topics else "general"), 0
    for topic in topics:
        hits = 0
        for keyword in topic.keywords:
            kw = keyword.lower()
            if not kw:
                continue
            if kw in title:
                hits += 2
            elif kw in body:
                hits += 1
        if hits > best_hits:
            best_key, best_hits = topic.key, hits
    return best_key, best_hits


def score(item: dict, topic_hits: int) -> float:
    recency = math.exp(-_days_old(item.get("published", "")) / 10.0)  # 半衰期约 7 天
    venue_bonus = 1.5 if item.get("venue") else 0.0
    weight = float(item.get("weight", 1.0))
    length_bonus = min(len(item.get("abstract", "")) / 2000.0, 1.0)
    return topic_hits * 1.0 + recency * 3.0 + venue_bonus + weight + length_bonus


def rank_papers(papers: list[dict], config: Config, limit: int | None = None) -> list[dict]:
    """按分数排序，同时保证方向多样性与方向内上限。"""
    limit = config.max_papers if limit is None else limit
    scored = []
    for item in dedupe(papers):
        topic_key, hits = assign_topic(item, config.topics)
        enriched = {**item, "topic": config.topic_label(topic_key), "topic_key": topic_key, "score": round(score(item, hits), 3)}
        scored.append(enriched)
    scored.sort(key=lambda i: i["score"], reverse=True)

    topic_count = max(1, len(config.topics))
    # 方向内上限：避免某一方向占满整期（6 篇 / 3 方向 => 最多 3 篇）
    per_topic_cap = max(2, -(-limit // topic_count) + 1)

    picked: list[dict] = []
    seen: set[str] = set()
    counts: dict[str, int] = {}

    def take(item: dict) -> None:
        picked.append(item)
        seen.add(item["id"])
        counts[item["topic_key"]] = counts.get(item["topic_key"], 0) + 1

    # 1) 每个方向先占一席，保证多面性
    for topic in config.topics:
        if len(picked) >= limit:
            break
        for item in scored:
            if item["topic_key"] == topic.key and item["id"] not in seen:
                take(item)
                break

    # 2) 按分数补齐，受方向上限约束
    for item in scored:
        if len(picked) >= limit:
            break
        if item["id"] in seen:
            continue
        if counts.get(item["topic_key"], 0) >= per_topic_cap:
            continue
        take(item)

    return picked[:limit]


def rank_news(news: list[dict], config: Config, limit: int = 8) -> list[dict]:
    """动态同样要有多面性：先保证 competitor/vendor/industry 各一条，再限单源条数。"""
    scored = []
    for item in dedupe(news):
        topic_key, hits = assign_topic(item, config.topics)
        value = float(item.get("weight", 1.0)) * 2 + hits + math.exp(-_days_old(item.get("published", "")) / 5.0) * 3
        scored.append({**item, "topic": config.topic_label(topic_key), "topic_key": topic_key, "score": round(value, 3)})
    scored.sort(key=lambda i: i["score"], reverse=True)

    per_source_cap = max(2, -(-limit // 3))
    picked: list[dict] = []
    seen: set[str] = set()
    counts: dict[str, int] = {}

    def take(item: dict) -> None:
        picked.append(item)
        seen.add(item["id"])
        counts[item["source"]] = counts.get(item["source"], 0) + 1

    for kind in ("competitor", "vendor", "industry"):
        if len(picked) >= limit:
            break
        for item in scored:
            if item.get("kind") == kind and item["id"] not in seen:
                take(item)
                break

    for item in scored:
        if len(picked) >= limit:
            break
        if item["id"] in seen:
            continue
        if counts.get(item["source"], 0) >= per_source_cap:
            continue
        take(item)

    return picked[:limit]
