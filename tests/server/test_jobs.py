import time

from server.db import connect, init_schema
from server.jobs import JobRunner


def wait_done(conn, jid, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        row = conn.execute(
            "select status, progress from jobs where id = ?", (jid,)).fetchone()
        if row["status"] in ("succeeded", "failed"):
            return row
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_job_succeeds_and_reports_progress(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    runner = JobRunner(conn)
    runner.start()
    try:
        jid = runner.submit("issue", "x", lambda ctx: ctx.set_progress(100, "done"))
        row = wait_done(conn, jid)
        assert row["status"] == "succeeded"
        assert row["progress"] == 100
    finally:
        runner.stop()


def test_job_failure_is_recorded(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    runner = JobRunner(conn)
    runner.start()
    try:
        def boom(ctx):
            raise RuntimeError("boom")

        jid = runner.submit("issue", "x", boom)
        row = wait_done(conn, jid)
        assert row["status"] == "failed"
        err = conn.execute("select error from jobs where id = ?", (jid,)).fetchone()["error"]
        assert "boom" in err
    finally:
        runner.stop()


def test_jobs_run_serially(db_file):
    """单 worker：两个任务不会交错。"""
    conn = connect(str(db_file))
    init_schema(conn)
    runner = JobRunner(conn)
    runner.start()
    order = []
    try:
        a = runner.submit("issue", "a", lambda ctx: (order.append("a-start"), time.sleep(0.05), order.append("a-end")))
        b = runner.submit("issue", "b", lambda ctx: order.append("b"))
        wait_done(conn, a)
        wait_done(conn, b)
        assert order == ["a-start", "a-end", "b"]
    finally:
        runner.stop()


def test_job_route_returns_row(client):
    conn = client.app.state.conn
    conn.execute(
        "insert into jobs(id,type,ref_id,status,progress,message,created_at) "
        "values ('j1','issue','x','running',42,'working','now')")
    conn.commit()
    r = client.get("/api/v1/jobs/j1")
    assert r.status_code == 200
    body = r.json()
    assert body["progress"] == 42
    assert body["message"] == "working"
