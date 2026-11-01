import sqlite3

import pytest

from server.db import connect, init_schema

EXPECTED = {
    "settings", "topics", "sources", "issues", "papers",
    "issue_papers", "news", "deep_reads", "repro_plans", "jobs",
}


def test_init_creates_all_tables(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    got = {r["name"] for r in conn.execute(
        "select name from sqlite_master where type='table'")}
    assert EXPECTED <= got


def test_settings_is_singleton(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    conn.execute("insert into settings(id) values (1)")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("insert into settings(id) values (2)")
        conn.commit()


def test_foreign_keys_are_enforced(db_file):
    conn = connect(str(db_file))
    init_schema(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "insert into issue_papers(issue_id, paper_id) values ('nope', 'nope')")
        conn.commit()
