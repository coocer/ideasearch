import pytest

from ideasearch.collect import Collected
from server.db import connect, init_schema
from server.pipeline import generate_issue
from server.settings import SettingsStore


class FakeCtx:
    def __init__(self):
        self.last = None

    def set_progress(self, pct, message=""):
        self.last = (pct, message)


def fake_collector(cfg):
    return Collected(
        papers=[{
            "id": f"p{i}", "external_id": f"p{i}", "title": f"T{i}",
            "abstract": "A", "kind": "paper", "published": "2026-10-30",
            "source": "arXiv", "url": f"u{i}", "authors": ["A"],
            "categories": ["cs.LG"], "comment": "",
        } for i in range(6)],
        news=[], warnings=[], conferences=[],
    )


class OkClient:
    available = True
    model = "fake"

    def chat_json(self, messages, **kwargs):
        return {
            "one_line": "一句话结论",
            "core_problem": "内容" * 60,
            "technique": "内容" * 60,
            "results": "内容" * 60,
            "outlook": "内容" * 60,
        }


def _store(db_file, **extra):
    conn = connect(str(db_file))
    init_schema(conn)
    s = SettingsStore(conn)
    s.update({"llm_api_key": "sk-x", **extra})
    return conn, s


def test_generates_issue_with_papers(db_file):
    conn, s = _store(db_file, min_papers=3)
    iid = generate_issue(conn, s.to_config(), FakeCtx(), s.target_words(),
                         collector=fake_collector, client=OkClient())
    rows = conn.execute("select * from issue_papers where issue_id = ?", (iid,)).fetchall()
    assert len(rows) == 6
    assert all(r["summary_status"] == "ok" for r in rows)
    issue = conn.execute("select * from issues where id = ?", (iid,)).fetchone()
    assert issue["status"] == "succeeded"
    assert issue["target_words"] > 0


def test_failed_paper_is_excluded(db_file):
    conn, s = _store(db_file, min_papers=1)

    class Picky(OkClient):
        def chat_json(self, messages, **kwargs):
            raise RuntimeError("bad json")

    iid = generate_issue(conn, s.to_config(), FakeCtx(), s.target_words(),
                         collector=fake_collector, client=Picky())
    rows = conn.execute("select * from issue_papers where issue_id = ?", (iid,)).fetchall()
    ok = [r for r in rows if r["summary_status"] == "ok"]
    assert ok == []
    issue = conn.execute("select * from issues where id = ?", (iid,)).fetchone()
    assert issue["status"] == "failed"


def test_no_api_key_is_rejected(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    s = SettingsStore(conn)

    class NoKeyClient(OkClient):
        available = False

        def chat_json(self, messages, **kwargs):
            raise AssertionError("没有 key 时不应调用模型")

    with pytest.raises(ValueError):
        generate_issue(conn, s.to_config(), FakeCtx(), s.target_words(),
                       collector=fake_collector, client=NoKeyClient())


def test_reuses_paper_across_issues(db_file):
    """同一篇论文第二次出现时复用 papers 行，不重复插入。"""
    conn, s = _store(db_file, min_papers=1)
    generate_issue(conn, s.to_config(), FakeCtx(), s.target_words(),
                   collector=fake_collector, client=OkClient())
    generate_issue(conn, s.to_config(), FakeCtx(), s.target_words(),
                   collector=fake_collector, client=OkClient())
    count = conn.execute("select count(*) as c from papers").fetchone()["c"]
    assert count == 6
