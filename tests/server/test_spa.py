"""SPA 托管：静态资源 + 深链接回落到 index.html。

BrowserRouter 下直接访问 /issues/xxx 必须返回 index.html，
否则硬刷新会得到 404（评审 Important）。
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.testclient import TestClient

from server.app import create_app


def _fake_dist() -> Path:
    dist = Path(__file__).resolve().parent / "_artifacts" / f"dist-{uuid.uuid4().hex}"
    dist.mkdir(parents=True)
    (dist / "assets").mkdir()
    (dist / "index.html").write_text("<html>spa-shell</html>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    return dist


def test_deep_link_serves_index_html(db_file):
    client = TestClient(create_app(str(db_file), spa_dir=str(_fake_dist())))
    for path in ("/issues/abc", "/read/p1", "/history"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "spa-shell" in response.text, path


def test_static_asset_is_served(db_file):
    client = TestClient(create_app(str(db_file), spa_dir=str(_fake_dist())))
    response = client.get("/assets/app.js")
    assert response.status_code == 200
    assert "console.log" in response.text


def test_api_paths_are_not_swallowed(db_file):
    client = TestClient(create_app(str(db_file), spa_dir=str(_fake_dist())))
    assert client.get("/api/v1/health").status_code == 200
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert "spa-shell" not in response.text
