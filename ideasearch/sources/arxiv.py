"""arXiv Atom API 采集。

官方接口：http://export.arxiv.org/api/query
注意其对 UA 与请求频率有要求，默认每次请求间隔 3 秒。
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from ..http import HttpError, get_text

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
API = "https://export.arxiv.org/api/query"

_WS = re.compile(r"\s+")


def _clean(text: str | None) -> str:
    return _WS.sub(" ", text or "").strip()


def _entry_to_dict(entry: ET.Element) -> dict:
    raw_id = _clean(entry.findtext(f"{ATOM}id"))
    arxiv_id = raw_id.rsplit("/abs/", 1)[-1]
    arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
    published = _clean(entry.findtext(f"{ATOM}published"))
    authors = [_clean(a.findtext(f"{ATOM}name")) for a in entry.findall(f"{ATOM}author")]
    categories = [c.get("term", "") for c in entry.findall(f"{ATOM}category")]
    primary = entry.find(f"{ARXIV_NS}primary_category")
    return {
        "id": arxiv_id,
        "source": "arXiv",
        "kind": "paper",
        "title": _clean(entry.findtext(f"{ATOM}title")),
        "abstract": _clean(entry.findtext(f"{ATOM}summary")),
        "url": f"https://arxiv.org/abs/{arxiv_id}",
        "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
        "published": published[:10],
        "updated": _clean(entry.findtext(f"{ATOM}updated"))[:10],
        "authors": authors[:12],
        "categories": categories,
        "primary_category": primary.get("term", "") if primary is not None else (categories[0] if categories else ""),
        "comment": _clean(entry.findtext(f"{ARXIV_NS}comment")),
        "journal_ref": _clean(entry.findtext(f"{ARXIV_NS}journal_ref")),
    }


def _query(search_query: str, max_results: int, timeout: float) -> list[dict]:
    url = (
        f"{API}?search_query={quote_plus(search_query)}"
        f"&start=0&max_results={max_results}"
        "&sortBy=submittedDate&sortOrder=descending"
    )
    xml = get_text(url, timeout=timeout, retries=3)
    root = ET.fromstring(xml)
    return [_entry_to_dict(e) for e in root.findall(f"{ATOM}entry")]


def fetch(
    *,
    categories: list[str],
    keywords: list[str] | None = None,
    max_results: int = 150,
    days_back: int = 7,
    delay: float = 3.0,
    timeout: float = 60,
) -> list[dict]:
    """抓取最近 days_back 天、指定分类/关键词的论文，按 id 去重。"""
    since = datetime.now(timezone.utc) - timedelta(days=days_back)
    collected: dict[str, dict] = {}

    cat_query = " OR ".join(f"cat:{c}" for c in categories) if categories else "cat:cs.LG"
    try:
        for item in _query(f"({cat_query})", max_results, timeout):
            collected.setdefault(item["id"], item)
    except (HttpError, ET.ParseError) as exc:
        raise HttpError(f"arXiv 分类检索失败: {exc}") from exc

    keywords = [k for k in (keywords or []) if k.strip()]
    if keywords:
        time.sleep(delay)
        kw_query = " OR ".join(f'all:"{k}"' for k in keywords[:8])
        try:
            for item in _query(f"({kw_query})", max(20, max_results // 3), timeout):
                collected.setdefault(item["id"], item)
        except (HttpError, ET.ParseError):
            pass  # 关键词检索是增强项，失败不致命

    # 时间窗过滤
    kept = []
    for item in collected.values():
        try:
            published = datetime.strptime(item["published"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            kept.append(item)
            continue
        if published >= since:
            kept.append(item)
    return kept
