"""配置加载：config.toml（stdlib tomllib）+ .env / 环境变量。"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict[str, Any] = {
    "report": {
        "title": "周观察报告",
        "output_dir": "output",
        "max_papers": 8,
        "min_papers": 5,
        "target_words": 600,
        "timezone": "Asia/Shanghai",
    },
    "arxiv": {
        "categories": ["cs.LG", "cs.CL", "cs.DC", "cs.AR"],
        "max_results": 150,
        "days_back": 7,
        "delay_seconds": 3.0,
        "keywords": [],
    },
    "topics": {},
    "feeds": [],
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_dotenv(path: Path) -> None:
    """把 .env 里的 KEY=VALUE 读进 os.environ（已存在的环境变量优先）。"""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(slots=True)
class Feed:
    name: str
    url: str
    kind: str = "industry"  # industry | competitor | vendor
    weight: float = 1.0
    limit: int = 15


@dataclass(slots=True)
class Topic:
    key: str
    label: str
    keywords: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Config:
    raw: dict[str, Any]
    topics: list[Topic]
    feeds: list[Feed]
    root: Path = ROOT

    # ---- report ----
    @property
    def title(self) -> str:
        return str(self.raw["report"]["title"])

    @property
    def output_dir(self) -> Path:
        return self.root / str(self.raw["report"]["output_dir"])

    @property
    def max_papers(self) -> int:
        return int(self.raw["report"]["max_papers"])

    @property
    def min_papers(self) -> int:
        return int(self.raw["report"]["min_papers"])

    @property
    def target_words(self) -> int:
        return int(self.raw["report"]["target_words"])

    # ---- arxiv ----
    @property
    def arxiv(self) -> dict[str, Any]:
        return self.raw["arxiv"]

    def topic_label(self, key: str) -> str:
        for topic in self.topics:
            if topic.key == key:
                return topic.label
        return key


def load_config(path: Path | None = None) -> Config:
    """读 config.toml，缺省值兜底；缺文件时用内置默认值。"""
    path = path or (ROOT / "config.toml")
    raw: dict[str, Any] = {}
    if path.is_file():
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    merged = _deep_merge(DEFAULTS, raw)

    topics = [
        Topic(key=key, label=str(value.get("label", key)), keywords=[str(k) for k in value.get("keywords", [])])
        for key, value in (merged.get("topics") or {}).items()
        if isinstance(value, dict)
    ]
    feeds = [
        Feed(
            name=str(item["name"]),
            url=str(item["url"]),
            kind=str(item.get("kind", "industry")),
            weight=float(item.get("weight", 1.0)),
            limit=int(item.get("limit", 15)),
        )
        for item in (merged.get("feeds") or [])
        if isinstance(item, dict) and item.get("name") and item.get("url")
    ]
    return Config(raw=merged, topics=topics, feeds=feeds, root=ROOT)
