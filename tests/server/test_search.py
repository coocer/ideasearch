"""Web Search 源必须真的参与采集（否则界面承诺不成立）。"""

from server.search import build_queries, collect_search, to_items
from server.settings import SettingsStore
from server.db import connect, init_schema
from ideasearch.config import Topic


def test_build_queries_uses_topic_keywords():
    topics = [Topic("inference", "推理优化", ["kv cache", "serving", "extra"]),
              Topic("empty", "空方向", [])]
    assert build_queries(topics, per_topic=2) == ["kv cache serving"]


def test_results_become_items():
    results = [
        {"title": "A", "url": "https://x/1", "summary": "要点", "date": "2026-10-30"},
        {"title": "", "url": "https://x/2"},
        {"title": "B", "url": ""},
    ]
    items = to_items(results)
    assert len(items) == 1
    assert items[0]["title"] == "A"
    assert items[0]["abstract"] == "要点"
    assert items[0]["published"] == "2026-10-30"


def test_collect_swallows_single_query_failure():
    calls = {"n": 0}

    def flaky(url, payload, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return {"results": [{"title": "T", "url": "https://x", "summary": "s"}]}

    warnings: list[str] = []
    items = collect_search(["q1", "q2"], api_key="k", post_json=flaky, warnings=warnings)
    assert len(items) == 1
    assert warnings and "q1" in warnings[0]


def test_to_config_exposes_search_block(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    s = SettingsStore(conn)
    conn.execute("insert into sources(kind,name,url,config,weight,enabled) values "
                 "('search','DeepSeek Search','','{\"count\":8}',1,1)")
    conn.execute("insert into topics(key,label,keywords,weight,enabled) values "
                 "('inference','推理优化','[\"kv cache\"]',1,1)")
    conn.commit()

    cfg = s.to_config()
    assert cfg.raw["search"]["enabled"] is True
    assert cfg.raw["search"]["queries"] == ["kv cache"]


def test_to_config_search_disabled_without_rows(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    s = SettingsStore(conn)
    cfg = s.to_config()
    assert cfg.raw["search"]["enabled"] is False
