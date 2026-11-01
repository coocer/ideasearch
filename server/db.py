"""SQLite 连接与建表。

并发：FastAPI 的同步路由跑在线程池里，而任务队列另有工作线程，共用同一个连接。
所有写操作必须经同一把锁，否则一个线程的 commit 会把另一个线程写了一半的事务提交出去。
`connect()` 返回的包装对象把这把锁加在每个写操作上。
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


class LockedConnection:
    """串行化同一个 sqlite3 连接上的执行，避免跨线程写冲突。"""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.lock = threading.RLock()

    def execute(self, sql: str, params=()):
        with self.lock:
            return self._conn.execute(sql, params)

    def executemany(self, sql: str, rows):
        with self.lock:
            return self._conn.executemany(sql, rows)

    def executescript(self, script: str):
        with self.lock:
            return self._conn.executescript(script)

    def commit(self) -> None:
        with self.lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self.lock:
            self._conn.rollback()

    def close(self) -> None:
        with self.lock:
            self._conn.close()

    def __getattr__(self, name: str):
        return getattr(self._conn, name)


def connect(db_path: str) -> LockedConnection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return LockedConnection(conn)


def init_schema(conn) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
