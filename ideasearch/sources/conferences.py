"""顶会日历与录用信息识别。

用途有两个：
1. 判断「最近是否在某个顶会窗口」，提醒当期报告补充该会论文；
2. 从 arXiv 的 comment 字段识别 "accepted by NeurIPS 2025" 之类的录用信息并加分。
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

# 依据团队关注方向整理；月份固定，年份按当前年推断（跨年自动 +1）。
CONFERENCES: list[dict] = [
    {"name": "ICLR", "area": "模型", "month": 4, "day": 24, "end_month": 5, "end_day": 1},
    {"name": "CVPR", "area": "模型", "month": 6, "day": 15, "end_month": 6, "end_day": 22},
    {"name": "ACL", "area": "模型", "month": 7, "day": 27, "end_month": 8, "end_day": 3},
    {"name": "ICML", "area": "模型", "month": 7, "day": 15, "end_month": 7, "end_day": 24},
    {"name": "KDD", "area": "模型", "month": 8, "day": 3, "end_month": 8, "end_day": 9},
    {"name": "SIGMOD", "area": "存储&云原生", "month": 6, "day": 22, "end_month": 6, "end_day": 27},
    {"name": "VLDB", "area": "存储&云原生", "month": 8, "day": 25, "end_month": 9, "end_day": 5},
    {"name": "USENIX ATC", "area": "存储&云原生", "month": 7, "day": 7, "end_month": 7, "end_day": 9},
    {"name": "SOSP", "area": "存储&云原生", "month": 10, "day": 13, "end_month": 10, "end_day": 16},
    {"name": "ACM MM", "area": "模型", "month": 10, "day": 27, "end_month": 11, "end_day": 3},
    {"name": "NeurIPS", "area": "模型", "month": 12, "day": 2, "end_month": 12, "end_day": 7},
    {"name": "AAAI", "area": "模型", "month": 2, "day": 20, "end_month": 2, "end_day": 27},
]

_VENUE_RE = re.compile(
    r"\b(NeurIPS|ICLR|ICML|CVPR|ACL|EMNLP|KDD|SIGMOD|VLDB|ICDE|FAST|OSDI|SOSP|ATC|ACM\s*MM|AAAI|ICCV|ECCV)\b",
    re.IGNORECASE,
)
_ACCEPT_RE = re.compile(
    r"(accept(ed)?|to\s+appear|camera[- ]ready|oral|spotlight)",
    re.IGNORECASE,
)

# 规范化展示名（正则匹配后统一大小写）
_DISPLAY = {
    "neurips": "NeurIPS",
    "iclr": "ICLR",
    "icml": "ICML",
    "cvpr": "CVPR",
    "iccv": "ICCV",
    "eccv": "ECCV",
    "acl": "ACL",
    "emnlp": "EMNLP",
    "aaai": "AAAI",
    "kdd": "KDD",
    "sigmod": "SIGMOD",
    "vldb": "VLDB",
    "icde": "ICDE",
    "fast": "FAST",
    "osdi": "OSDI",
    "sosp": "SOSP",
    "atc": "USENIX ATC",
    "acmmm": "ACM MM",
}


def _window(year: int, conf: dict) -> tuple[date, date]:
    start = date(year, conf["month"], conf["day"])
    end_month, end_day = conf.get("end_month", conf["month"]), conf.get("end_day", conf["day"])
    end = date(year + (1 if end_month < conf["month"] else 0), end_month, end_day)
    return start, end


def active_conferences(today: date | None = None, lead_days: int = 21) -> list[dict]:
    """返回当前处于窗口期（或 lead_days 天内即将开始）的会议。"""
    today = today or datetime.now(timezone.utc).date()
    hits = []
    for conf in CONFERENCES:
        for year in (today.year - 1, today.year, today.year + 1):
            start, end = _window(year, conf)
            if start - timedelta(days=lead_days) <= today <= end + timedelta(days=7):
                hits.append({**conf, "start": start.isoformat(), "end": end.isoformat(), "year": year})
                break
    return sorted(hits, key=lambda c: c["start"])


def display_venue(raw: str | None) -> str:
    """把识别到的会议名规范成统一展示写法（NeurIPS / USENIX ATC / ACM MM ...）。"""
    text = (raw or "").strip()
    if not text:
        return ""
    key = re.sub(r"[\s\-]", "", text).lower()
    return _DISPLAY.get(key, text.upper() if text.isupper() else text)


def detect_venue(text: str | None) -> str | None:
    """从 comment / 标题中识别顶会录用信息。"""
    text = text or ""
    if not _ACCEPT_RE.search(text):
        return None
    match = _VENUE_RE.search(text)
    if not match:
        return None
    return display_venue(match.group(1))
