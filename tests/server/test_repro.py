from server.db import connect, init_schema
from server.prompts import validate_repro
from server.repro import get_cached, store

BASE = {
    "evidence": {"level": "none", "note": "无代码链接"},
    "likelihood": "中",
    "estimate": {"token_range": [1200000, 2500000],
                 "time_range_days": [3, 5],
                 "assumptions": ["单机双进程"]},
    "missing": ["带宽未披露"],
    "plan_md": "1. 搭最小拓扑",
    "handoff_prompt": "请实现一个最小可运行原型…",
}


def test_valid_repro_passes():
    assert validate_repro(BASE) == []


def test_level_must_be_enum():
    bad = {**BASE, "evidence": {"level": "unknown", "note": ""}}
    assert validate_repro(bad) != []


def test_estimate_ranges_must_be_ordered():
    bad = {**BASE, "estimate": {**BASE["estimate"], "token_range": [5, 1]}}
    assert validate_repro(bad) != []


def test_missing_section_is_flagged():
    bad = {k: v for k, v in BASE.items() if k != "missing"}
    assert validate_repro(bad) != []


def test_empty_handoff_is_flagged():
    bad = {**BASE, "handoff_prompt": "   "}
    assert validate_repro(bad) != []


def test_cache_is_per_paper_and_model(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    conn.execute("insert into papers(id, external_id) values ('p1', 'e1')")
    conn.commit()
    store(conn, "p1", "deepseek-flash", BASE)
    assert get_cached(conn, "p1", "deepseek-flash") is not None
    assert get_cached(conn, "p1", "other-model") is None
