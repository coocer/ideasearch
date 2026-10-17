"""RSS / Atom 采集（公众号转载源、技术博客、厂商博客）。"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from ..http import HttpError, get_text

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
ATOM = "{http://www.w3.org/2005/Atom}"


def strip_html(text: str | None) -> str:
    """去标签 + 反转义 + 压缩空白。"""
    return _WS.sub(" ", html.unescape(_TAG.sub(" ", text or ""))).strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _first_text(node: ET.Element, names: set[str]) -> str:
    for child in node:
        if _local(child.tag) in names and child.text:
            return child.text
    return ""


def _to_iso(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value[:10]


def parse_feed(xml: str, *, name: str, kind: str, weight: float, limit: int = 15) -> list[dict]:
    """解析 RSS2.0 / Atom，返回统一结构。"""
    root = ET.fromstring(xml)
    items: list[dict] = []

    for node in root.iter():
        tag = _local(node.tag)
        if tag not in ("item", "entry"):
            continue
        title = strip_html(_first_text(node, {"title"}))
        link = _first_text(node, {"link"})
        if not link:
            for child in node:
                if _local(child.tag) == "link" and child.get("href"):
                    link = child.get("href", "")
                    break
        summary = strip_html(
            _first_text(node, {"description", "summary", "content", "encoded", "content:encoded"})
        )
        published = _to_iso(_first_text(node, {"pubdate", "published", "updated", "date"}))
        if not title:
            continue
        items.append(
            {
                "id": link or f"{name}:{title}",
                "source": name,
                "kind": kind,
                "title": title,
                "abstract": summary[:1200],
                "url": link,
                "published": published,
                "weight": weight,
            }
        )
        if len(items) >= limit:
            break
    return items


def fetch(feed, *, timeout: float = 30) -> list[dict]:
    """抓取单个 feed；失败抛 HttpError，由调用方降级处理。"""
    try:
        xml = get_text(feed.url, timeout=timeout, retries=2)
        return parse_feed(xml, name=feed.name, kind=feed.kind, weight=feed.weight, limit=feed.limit)
    except ET.ParseError as exc:
        raise HttpError(f"{feed.name}: XML 解析失败 ({exc})") from exc
