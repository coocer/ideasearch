"""采集编排：逐个源抓取，单源失败降级为警告。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import http
from .config import Config
from .http import HttpError
from .sources import arxiv, conferences, rss


@dataclass(slots=True)
class Collected:
    papers: list[dict] = field(default_factory=list)
    news: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    conferences: list[dict] = field(default_factory=list)
    fetched_at: str = ""

    def to_json(self) -> dict:
        return {
            "fetched_at": self.fetched_at,
            "papers": self.papers,
            "news": self.news,
            "warnings": self.warnings,
            "conferences": self.conferences,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Collected":
        return cls(
            papers=data.get("papers", []),
            news=data.get("news", []),
            warnings=data.get("warnings", []),
            conferences=data.get("conferences", []),
            fetched_at=data.get("fetched_at", ""),
        )


def collect(config: Config) -> Collected:
    """跑一遍所有来源。"""
    result = Collected(fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    http.WARNINGS.clear()
    result.conferences = conferences.active_conferences()

    # 1) arXiv
    try:
        papers = arxiv.fetch(
            categories=list(config.arxiv.get("categories", [])),
            keywords=list(config.arxiv.get("keywords", [])),
            max_results=int(config.arxiv.get("max_results", 150)),
            days_back=int(config.arxiv.get("days_back", 7)),
            delay=float(config.arxiv.get("delay_seconds", 3.0)),
        )
        result.papers = papers
    except (HttpError, Exception) as exc:  # noqa: BLE001
        result.warnings.append(f"arXiv 采集失败：{exc}")

    # 2) RSS / Atom
    for feed in config.feeds:
        try:
            items = rss.fetch(feed)
            result.news.extend(items)
        except HttpError as exc:
            result.warnings.append(str(exc))
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"{feed.name} 采集异常：{exc}")

    # 3) 顶会录用信息补全（从 arXiv comment 里识别）
    for paper in result.papers:
        venue = conferences.detect_venue(paper.get("comment", "")) or conferences.detect_venue(paper.get("title", ""))
        if venue:
            paper["venue"] = venue

    result.warnings.extend(http.WARNINGS)
    return result


def save(result: Collected, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load(path: Path) -> Collected:
    return Collected.from_json(json.loads(path.read_text(encoding="utf-8")))
