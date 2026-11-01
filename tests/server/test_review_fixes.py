"""评审后修复的回归测试（对应 ledger 的 Final: fixed 条目）。"""

import json

from ideasearch.collect import Collected
from server.db import connect, init_schema
from server.pipeline import generate_issue
from server.settings import SettingsStore, build_client


# ---- 1. 配置接口必须存在，否则全新克隆永远无法配置 key ----

def test_settings_route_roundtrip(client):
    r = client.put("/api/v1/settings", json={
        "llm_api_key": "sk-abc", "llm_model": "m2",
        "background_json": {"role": "推理工程师"}})
    assert r.status_code == 200
    assert "sk-abc" not in str(r.json())
    assert r.json()["api_key_masked"] is True
    assert client.get("/api/v1/settings").json()["llm_model"] == "m2"


def test_settings_route_probe(client):
    client.put("/api/v1/settings", json={"llm_api_key": "sk-abc"})
    r = client.post("/api/v1/settings/test")
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ---- 2. 模型客户端必须读库里的配置，而不是环境变量 ----

def test_build_client_uses_stored_settings():
    c = build_client({
        "llm_api_key": "sk-k", "llm_base_url": "http://local",
        "llm_model": "m3"})
    assert c.api_key == "sk-k"
    assert c.base_url == "http://local"
    assert c.model == "m3"


# ---- 3. 抓取窗口必须真的生效 ----

def test_window_days_reaches_arxiv(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    s = SettingsStore(conn)
    s.update({"window_days": 14})
    conn.execute("insert into sources(kind, name, config) "
                 "values ('arxiv', 'arXiv', '{\"categories\":[\"cs.LG\"]}')")
    conn.commit()
    assert s.to_config().arxiv["days_back"] == 14


# ---- 4. 失败的整期不能被当成正常文章返回 ----

def test_failed_issue_is_not_served(seeded_issue):
    client, iid = seeded_issue()
    conn = client.app.state.conn
    conn.execute("update issues set status = 'failed' where id = ?", (iid,))
    conn.commit()
    assert client.get(f"/api/v1/issues/{iid}").status_code == 409
    assert client.get(f"/api/v1/issues/{iid}/export").status_code == 409


# ---- 5. 模型返回非对象时，整期必须收尾为 failed 而不是卡在 running ----

class _ListClient:
    available = True
    model = "fake"

    def chat_json(self, messages, **kwargs):
        return []  # 合法 JSON，但不是对象


def _collector(cfg):
    return Collected(
        papers=[{"id": "p1", "external_id": "e1", "title": "T",
                 "abstract": "A", "kind": "paper", "published": "2026-10-30",
                 "source": "arXiv", "url": "u", "authors": [], "categories": [],
                 "comment": ""}],
        news=[], warnings=[], conferences=[])


class _Ctx:
    def set_progress(self, pct, message=""):
        pass


def test_non_object_reply_does_not_leave_issue_running(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    s = SettingsStore(conn)
    s.update({"llm_api_key": "sk-x", "min_papers": 1})
    iid = generate_issue(conn, s.to_config(), _Ctx(), s.target_words(),
                         collector=_collector, client=_ListClient())
    status = conn.execute("select status from issues where id = ?", (iid,)).fetchone()["status"]
    assert status == "failed"


def test_failed_issue_records_reason(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    s = SettingsStore(conn)
    s.update({"llm_api_key": "sk-x", "min_papers": 1})
    iid = generate_issue(conn, s.to_config(), _Ctx(), s.target_words(),
                         collector=_collector, client=_ListClient())
    row = conn.execute("select error from issues where id = ?", (iid,)).fetchone()
    assert row["error"]


# ---- 6. 快照必须能解释当时按什么生成 ----

def test_snapshot_and_window_are_recorded(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    s = SettingsStore(conn)
    s.update({"llm_api_key": "sk-x", "min_papers": 1, "window_days": 14,
              "background_json": '{"role": "推理工程师"}'})
    iid = generate_issue(conn, s.to_config(), _Ctx(), s.target_words(),
                         collector=_collector, client=_ListClient(),
                         background={"role": "推理工程师"})
    row = conn.execute("select * from issues where id = ?", (iid,)).fetchone()
    assert row["window_days"] == 14
    snapshot = json.loads(row["config_snapshot"])
    assert snapshot["background"]["role"] == "推理工程师"
