from server.db import connect, init_schema
from server.settings import SettingsStore


def store(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    return SettingsStore(conn), conn


def test_defaults_and_masking(db_file):
    s, _ = store(db_file)
    s.update({"llm_api_key": "sk-secret", "llm_model": "deepseek-flash"})
    assert s.get()["api_key_masked"] is True
    assert "sk-secret" not in str(s.get())
    assert s.get_raw()["llm_api_key"] == "sk-secret"


def test_to_config_maps_topics_and_sources(db_file):
    s, conn = store(db_file)
    s.update({"share_minutes": 60, "words_per_minute": 150})
    conn.execute(
        "insert into topics(key,label,keywords,weight,enabled) "
        "values ('inference','推理优化','[\"kv cache\"]',3,1)")
    conn.execute(
        "insert into sources(kind,name,url,config,weight,enabled) "
        "values ('arxiv','arXiv','','{\"categories\":[\"cs.LG\"]}',1,1)")
    conn.commit()
    cfg = s.to_config()
    assert cfg.title == "周观察报告"
    assert cfg.topics[0].key == "inference"
    assert cfg.topics[0].weight == 3
    assert cfg.arxiv["categories"] == ["cs.LG"]
    assert s.target_words() == 9000


def test_not_ready_without_key(db_file):
    s, _ = store(db_file)
    assert s.is_ready() is False


def test_ready_with_key(db_file):
    s, _ = store(db_file)
    s.update({"llm_api_key": "sk-x"})
    assert s.is_ready() is True


def test_update_ignores_unknown_fields(db_file):
    s, _ = store(db_file)
    s.update({"nope": "x", "window_days": 14})
    assert s.get_raw()["window_days"] == 14


def test_no_key_masks_to_empty(db_file):
    """没有 key 时不能返回 sk-***，否则前端以为已配置。"""
    s, _ = store(db_file)
    got = s.get()
    assert got["api_key_masked"] is False
    assert got["llm_api_key"] == ""


def test_key_present_masks(db_file):
    s, _ = store(db_file)
    s.update({"llm_api_key": "sk-real"})
    got = s.get()
    assert got["api_key_masked"] is True
    assert got["llm_api_key"] == "sk-***"
