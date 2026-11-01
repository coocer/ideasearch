from fastapi.testclient import TestClient

from server.app import create_app


def test_health(db_file):
    client = TestClient(create_app(str(db_file)))
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
