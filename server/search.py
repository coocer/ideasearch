"""Web Search 数据源：用 DeepSeek Search API 把"方向关键词"变成条目。

这条路径的意义：不想配 arXiv 分类和 RSS 的人，只开搜索源也能出文章。
"""

from __future__ import annotations

import uuid

from ideasearch.http import post_json as default_post_json

SEARCH_ENDPOINT = "https://api.deepseek.com/v1/tools/search"


def build_queries(topics, per_topic: int = 2) -> list[str]:
    """每个方向取前几个关键词拼一条查询。"""
    queries: list[str] = []
    for topic in topics:
        words = [str(k).strip() for k in topic.keywords if str(k).strip()]
        if not words:
            continue
        queries.append(" ".join(words[:per_topic]))
    return queries


def fetch_results(
    query: str,
    *,
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    count: int = 8,
    post_json=None,
) -> list[dict]:
    post_json = post_json or default_post_json
    data = post_json(
        f"{base_url.rstrip('/')}/v1/tools/search",
        {"query": query, "count": count, "need_content": False},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return list((data or {}).get("results") or [])


def to_items(results: list[dict], *, source_name: str = "Web Search") -> list[dict]:
    """把搜索结果转成和 RSS 条目同构的形状，好进排序。"""
    items: list[dict] = []
    for row in results:
        url = str(row.get("url") or "").strip()
        title = str(row.get("title") or "").strip()
        if not url or not title:
            continue
        summary = str(row.get("summary") or row.get("snippet") or "").strip()
        items.append({
            "id": url or uuid.uuid4().hex,
            "source": source_name,
            "kind": "industry",
            "title": title,
            "abstract": summary,
            "url": url,
            "published": str(row.get("date") or "")[:10],
            "weight": 1.0,
        })
    return items


def collect_search(
    queries: list[str],
    *,
    api_key: str,
    base_url: str = "https://api.deepseek.com",
    count: int = 8,
    post_json=None,
    warnings: list[str] | None = None,
) -> list[dict]:
    """逐个查询抓取；单条失败只记告警，不打断整期。"""
    items: list[dict] = []
    for query in queries:
        try:
            items.extend(to_items(
                fetch_results(query, api_key=api_key, base_url=base_url, count=count, post_json=post_json)
            ))
        except Exception as exc:  # noqa: BLE001
            if warnings is not None:
                warnings.append(f"Web Search「{query}」失败：{exc}")
    return items
