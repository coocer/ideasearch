"""任务进度查询。"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..errors import not_found

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(request: Request, job_id: str) -> dict:
    row = request.app.state.conn.execute(
        "select * from jobs where id = ?", (job_id,)).fetchone()
    if row is None:
        raise not_found("任务")
    return {
        "id": row["id"],
        "type": row["type"],
        "refId": row["ref_id"],
        "status": row["status"],
        "progress": row["progress"],
        "message": row["message"],
        "error": row["error"],
    }
