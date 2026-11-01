def test_export_escapes_pipe_in_title(seeded_issue):
    client, iid = seeded_issue(title="KV | Cache 优化")
    r = client.get(f"/api/v1/issues/{iid}/export")
    assert r.status_code == 200
    assert "KV \\| Cache" in r.text


def test_export_contains_deepread_when_present(seeded_issue):
    client, iid = seeded_issue(with_deepread=True)
    body = client.get(f"/api/v1/issues/{iid}/export").text
    assert "深读" in body


def test_export_without_deepread_has_no_deepread_section(seeded_issue):
    client, iid = seeded_issue()
    body = client.get(f"/api/v1/issues/{iid}/export").text
    assert "深读" not in body


def test_list_and_detail(seeded_issue):
    client, iid = seeded_issue()
    items = client.get("/api/v1/issues").json()["items"]
    assert items[0]["id"] == iid
    detail = client.get(f"/api/v1/issues/{iid}").json()
    assert detail["papers"][0]["title"] == "示例论文"


def test_export_unknown_issue_is_404(client):
    r = client.get("/api/v1/issues/nope/export")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
