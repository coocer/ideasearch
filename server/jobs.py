"""单 worker 任务队列（spec 十一：job 之间串行，job 内部再并发）。

串行不只是省事：SQLite 单文件写入经同一把锁，避免并发写冲突。
"""

from __future__ import annotations

import queue
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobContext:
    """交给任务体使用：只有进度上报。"""

    def __init__(self, runner: "JobRunner", job_id: str) -> None:
        self._runner = runner
        self.job_id = job_id

    def set_progress(self, pct: int, message: str = "") -> None:
        self._runner._update(self.job_id, progress=int(pct), message=message)


class JobRunner:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._lock = threading.Lock()
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None

    # ---------- 生命周期 ----------
    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="job-runner", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._queue.put(None)
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    # ---------- 对外 ----------
    def submit(self, kind: str, ref_id: str, work: Callable[[JobContext], None]) -> str:
        with self._lock:
            # 同一目标的在飞任务直接复用：刷新/双击不该再开一个计费任务
            existing = self.conn.execute(
                "select id from jobs where type = ? and ref_id = ? "
                "and status in ('pending', 'running') order by created_at limit 1",
                (kind, ref_id),
            ).fetchone()
            if existing is not None:
                return existing["id"]

            job_id = uuid.uuid4().hex
            self.conn.execute(
                "insert into jobs(id, type, ref_id, status, progress, created_at) "
                "values (?, ?, ?, 'pending', 0, ?)",
                (job_id, kind, ref_id, _now()),
            )
            self.conn.commit()
        self._queue.put((job_id, work))
        return job_id

    # ---------- 内部 ----------
    def _update(self, job_id: str, **fields) -> None:
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with self._lock:
            self.conn.execute(
                f"update jobs set {assignments} where id = ?", [*fields.values(), job_id])
            self.conn.commit()

    def _loop(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            job_id, work = item
            self._update(job_id, status="running")
            try:
                work(JobContext(self, job_id))
            except Exception as exc:  # noqa: BLE001 - 任何失败都要落库
                self._update(job_id, status="failed", error=str(exc), finished_at=_now())
            else:
                self._update(job_id, status="succeeded", progress=100, finished_at=_now())
