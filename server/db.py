"""SQLite 连接与建表。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def connect(db_path: str) -> sqlite3.Connection:
    """打开连接：Row 访问 + 外键约束开启。

    check_same_thread=False 是必要的：任务在单独线程里执行，而连接建在主线程。
    所有写操作由 JobRunner 内部的锁串行化（见 server/jobs.py）。
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
