from server.db import connect, init_schema
from server.deepread import background_hash, get_cached, store
from server.fulltext import fetch_text
from server.prompts import validate_deepread


def _boom(*args, **kwargs):
    raise RuntimeError("nope")


def test_fetch_falls_back_to_abstract():
    text, status = fetch_text("https://arxiv.org/abs/2610.1", get_text=_boom, post_json=_boom)
    assert status == "abstract_only"
    assert text == ""


def test_fetch_uses_fetch_api_first():
    calls = {}

    def post(url, payload, **kwargs):
        calls["url"] = payload["url"]
        return {"content": "# 正文"}

    text, status = fetch_text("https://arxiv.org/abs/2610.1", get_text=_boom, post_json=post)
    assert status == "full"
    assert text == "# 正文"
    assert "arxiv.org/abs/2610.1" in calls["url"]


def _deep(**over):
    base = {
        "why_it_matters": "x",
        "background": "y",
        "what_they_did": "z",
        "why_it_works": "w",
        "limits": "v",
        "value_for_you": "能直接替换你现在的淘汰策略",
        "verdict": 3,
        "jargon": [["TTFT", "首 token 延迟"]],
        "claims": [{"text": "延迟降低 45%", "evidence": "表 2", "location": "§4.1"}],
    }
    base.update(over)
    return base


def test_validate_flags_unsourced_number():
    data = _deep(claims=[{"text": "延迟降低 45%", "evidence": "", "location": ""}])
    problems = validate_deepread(data)
    assert any("证据" in p for p in problems)


def test_validate_passes_with_locations():
    assert validate_deepread(_deep()) == []


def test_validate_rejects_vague_value():
    data = _deep(value_for_you="与该方向相关，值得关注")
    assert validate_deepread(data) != []


def test_validate_requires_all_sections():
    data = _deep()
    data.pop("limits")
    assert validate_deepread(data) != []


def test_cache_key_includes_background_hash(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    conn.execute("insert into papers(id, external_id) values ('p1', 'e1')")
    conn.commit()

    h1 = background_hash({"role": "推理工程师"})
    h2 = background_hash({"role": "算法研究员"})

    store(conn, "p1", h1, "deepseek-flash", _deep(), 1200)
    assert get_cached(conn, "p1", h1, "deepseek-flash") is not None
    assert get_cached(conn, "p1", h2, "deepseek-flash") is None
