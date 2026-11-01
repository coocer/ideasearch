def test_create_and_list_topic(client):
    r = client.post("/api/v1/topics", json={
        "key": "inference", "label": "推理优化",
        "keywords": ["kv cache"], "weight": 3})
    assert r.status_code == 201
    items = client.get("/api/v1/topics").json()["items"]
    assert items[0]["key"] == "inference"
    assert items[0]["keywords"] == ["kv cache"]


def test_duplicate_key_conflicts(client):
    body = {"key": "dup", "label": "X", "keywords": [], "weight": 1}
    client.post("/api/v1/topics", json=body)
    r = client.post("/api/v1/topics", json=body)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "TOPIC_KEY_CONFLICT"


def test_patch_updates_weight(client):
    client.post("/api/v1/topics", json={"key": "t1", "label": "T", "keywords": [], "weight": 1})
    r = client.patch("/api/v1/topics/t1", json={"weight": 3})
    assert r.status_code == 200
    assert r.json()["weight"] == 3


def test_delete_is_soft(client):
    client.post("/api/v1/topics", json={"key": "t1", "label": "T", "keywords": [], "weight": 1})
    assert client.delete("/api/v1/topics/t1").status_code == 204
    assert client.get("/api/v1/topics").json()["items"][0]["enabled"] is False


def test_create_and_delete_source(client):
    r = client.post("/api/v1/sources", json={
        "kind": "rss", "name": "量子位", "url": "https://example.test/feed",
        "config": {"feed_kind": "industry"}, "weight": 1.2})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert client.delete(f"/api/v1/sources/{sid}").status_code == 204
    assert client.get("/api/v1/sources").json()["items"][0]["enabled"] is False


def test_unknown_topic_is_404(client):
    r = client.patch("/api/v1/topics/nope", json={"weight": 2})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
