"""配置读写：SQLite 是唯一真相（spec 六.1 / 十五.6）。

`share_minutes` / `words_per_minute` 只活在这里，不进 `Config`——
领域层不因前端需求而改结构。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from ideasearch.config import ROOT, Config, Feed, Topic

#: 允许通过接口写入的列；未知字段一律忽略。
FIELDS = (
    "llm_base_url", "llm_api_key", "llm_model", "window_days", "background_json",
    "title", "share_minutes", "words_per_minute", "min_papers", "max_papers",
    "timezone", "arxiv_max_results", "arxiv_delay_seconds",
)

MASK = "sk-***"


def build_client(raw: dict):
    """按库里的配置构造模型客户端。

    直接调 DeepSeek() 会去读环境变量，导致「库里配了 key 却报未配置」（评审 Important）。
    """
    from ideasearch.llm import DeepSeek

    return DeepSeek(
        api_key=str(raw.get("llm_api_key") or ""),
        base_url=str(raw.get("llm_base_url") or "") or None,
        model=str(raw.get("llm_model") or "") or None,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SettingsStore:
    def __init__(self, conn) -> None:
        self.conn = conn

    # ---------- 读 ----------
    def _row(self):
        row = self.conn.execute("select * from settings where id = 1").fetchone()
        if row is None:
            self.conn.execute("insert into settings(id) values (1)")
            self.conn.commit()
            row = self.conn.execute("select * from settings where id = 1").fetchone()
        return row

    def get_raw(self) -> dict:
        row = self._row()
        return {name: row[name] for name in FIELDS}

    def get(self) -> dict:
        """给前端的视图：key 打码，另附 api_key_masked 标记。"""
        raw = self.get_raw()
        raw["api_key"] = MASK
        raw["llm_api_key"] = MASK
        raw["api_key_masked"] = True
        return raw

    def is_ready(self) -> bool:
        return bool(str(self.get_raw()["llm_api_key"] or "").strip())

    def target_words(self) -> int:
        raw = self.get_raw()
        return int(raw["share_minutes"]) * int(raw["words_per_minute"])

    # ---------- 写 ----------
    def update(self, payload: dict) -> dict:
        self._row()  # 确保单例行存在，否则 UPDATE 命中 0 行
        allowed = {k: v for k, v in payload.items() if k in FIELDS}
        # 前端回传打码值时不覆盖真实 key
        if allowed.get("llm_api_key") == MASK:
            allowed.pop("llm_api_key")
        if allowed:
            assignments = ", ".join(f"{k} = ?" for k in allowed)
            self.conn.execute(
                f"update settings set {assignments}, updated_at = ? where id = 1",
                [*allowed.values(), _now()],
            )
            self.conn.commit()
        return self.get()

    # ---------- 领域层视图 ----------
    def to_config(self) -> Config:
        raw = self.get_raw()
        topics = [
            Topic(row["key"], row["label"], json.loads(row["keywords"] or "[]"), float(row["weight"]))
            for row in self.conn.execute(
                "select * from topics where enabled = 1 order by id")
        ]

        # 窗口是设置项，即使没有任何 arxiv 源行也必须生效（评审：14 天被静默忽略）
        arxiv: dict = {
            "categories": [],
            "keywords": [],
            "max_results": int(raw["arxiv_max_results"]),
            "delay_seconds": float(raw["arxiv_delay_seconds"]),
            "days_back": int(raw["window_days"]),
        }
        feeds: list[Feed] = []
        for row in self.conn.execute("select * from sources where enabled = 1 order by id"):
            cfg = json.loads(row["config"] or "{}")
            if row["kind"] == "arxiv":
                arxiv = {
                    "categories": cfg.get("categories", []),
                    "keywords": cfg.get("keywords", []),
                    "max_results": int(raw["arxiv_max_results"]),
                    "delay_seconds": float(raw["arxiv_delay_seconds"]),
                    "days_back": int(raw["window_days"]),
                }
            elif row["kind"] == "rss":
                feeds.append(Feed(
                    name=row["name"], url=row["url"],
                    kind=cfg.get("feed_kind", "industry"),
                    weight=float(row["weight"]),
                ))

        return Config(
            raw={
                "report": {
                    "title": raw["title"],
                    "output_dir": "output",
                    "max_papers": int(raw["max_papers"]),
                    "min_papers": int(raw["min_papers"]),
                    "target_words": self.target_words(),
                    "timezone": raw["timezone"],
                },
                "arxiv": arxiv,
                "topics": {},
                "feeds": [],
            },
            topics=topics,
            feeds=feeds,
            root=ROOT,
        )
