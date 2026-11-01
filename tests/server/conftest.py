"""测试公共夹具。

环境说明：本机沙箱下「运行时新建的嵌套目录」无法被枚举，
因此测试不使用 pytest 的 `tmp_path`，改用仓库内固定目录下的唯一文件名。
见 .superpowers/sdd/.../progress.md 的 Ruling 2。
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import create_app

ARTIFACTS = Path(__file__).resolve().parent / "_artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


@pytest.fixture()
def db_file() -> Path:
    """本次测试独占的数据库文件路径（父目录已存在，不新建目录）。"""
    return ARTIFACTS / f"{uuid.uuid4().hex}.db"


@pytest.fixture()
def client(db_file) -> TestClient:
    with TestClient(create_app(str(db_file))) as c:
        yield c


@pytest.fixture()
def seeded_issue(client):
    """造一期含 1 篇论文（标题可指定）与可选深读记录。"""
    import json

    def make(title: str = "示例论文", with_deepread: bool = False):
        conn = client.app.state.conn
        conn.execute(
            "insert into issues(id, title, created_at, window_days, window_start, "
            "window_end, target_words, status) values ('i1', ?, '2026-11-01', 7, "
            "'2026-10-25', '2026-11-01', 9000, 'succeeded')",
            ("示例一期",),
        )
        conn.execute(
            "insert into papers(id, external_id, url, title, published) "
            "values ('p1', 'e1', 'https://arxiv.org/abs/1', ?, '2026-10-30')",
            (title,),
        )
        summary = json.dumps({
            "one_line": "一句话结论",
            "core_problem": "问题",
            "technique": "手段",
            "results": "效果",
            "outlook": "启发",
        }, ensure_ascii=False)
        conn.execute(
            "insert into issue_papers(issue_id, paper_id, topic_key, score, selected_rank, "
            "one_line, summary_json, summary_status) values "
            "('i1', 'p1', 'inference', 1.0, 1, '一句话结论', ?, 'ok')",
            (summary,),
        )
        if with_deepread:
            conn.execute(
                "insert into deep_reads(id, paper_id, background_hash, model, status, "
                "content_json, created_at) values ('d1', 'p1', 'h', 'm', 'succeeded', ?, 'now')",
                (json.dumps({"why_it_matters": "深读内容示例"}, ensure_ascii=False),),
            )
        conn.commit()
        return client, "i1"

    return make
