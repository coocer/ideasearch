"""首次引导要能从现有 config.toml 导入种子，否则空库等于不可用。"""


def test_first_save_seeds_topics_and_sources(client):
    conn = client.app.state.conn
    assert conn.execute("select count(*) as c from topics").fetchone()["c"] == 0

    response = client.put("/api/v1/settings", json={"llm_api_key": "sk-x", "llm_model": "deepseek-flash"})
    assert response.status_code == 200

    topics = conn.execute("select * from topics").fetchall()
    sources = conn.execute("select * from sources").fetchall()
    assert len(topics) >= 1
    assert any(row["kind"] == "arxiv" for row in sources)
    assert any(row["kind"] == "rss" for row in sources)


def test_seeding_is_idempotent(client):
    conn = client.app.state.conn
    client.put("/api/v1/settings", json={"llm_api_key": "sk-x"})
    first = conn.execute("select count(*) as c from topics").fetchone()["c"]
    client.put("/api/v1/settings", json={"llm_model": "deepseek-flash"})
    second = conn.execute("select count(*) as c from topics").fetchone()["c"]
    assert first == second


def test_seeding_keeps_user_topics(client):
    conn = client.app.state.conn
    client.post("/api/v1/topics", json={"key": "mine", "label": "我的方向", "keywords": []})
    client.put("/api/v1/settings", json={"llm_api_key": "sk-x"})
    keys = [row["key"] for row in conn.execute("select key from topics").fetchall()]
    assert keys == ["mine"]
