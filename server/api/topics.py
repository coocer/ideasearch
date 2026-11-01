"""研究方向 CRUD。key 不可变，删除是软删。"""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Request

from ..errors import ApiError, not_found

router = APIRouter(prefix="/topics", tags=["topics"])


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "key": row["key"],
        "label": row["label"],
        "keywords": json.loads(row["keywords"] or "[]"),
        "weight": row["weight"],
        "enabled": bool(row["enabled"]),
    }


def _conn(request: Request):
    return request.app.state.conn


@router.get("")
def list_topics(request: Request) -> dict:
    rows = _conn(request).execute("select * from topics order by id").fetchall()
    items = [_row_to_dict(r) for r in rows]
    return {"items": items, "total": len(items), "page": 1, "pageSize": len(items)}


@router.post("", status_code=201)
def create_topic(request: Request, body: dict) -> dict:
    conn = _conn(request)
    key = str(body.get("key", "")).strip()
    if not key:
        raise ApiError(400, "INVALID_KEY", "key 不能为空")
    try:
        cur = conn.execute(
            "insert into topics(key, label, keywords, weight, enabled) values (?,?,?,?,?)",
            (key, body.get("label", key), json.dumps(body.get("keywords", []), ensure_ascii=False),
             float(body.get("weight", 1)), 1 if body.get("enabled", True) else 0),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        raise ApiError(409, "TOPIC_KEY_CONFLICT", "该方向 key 已存在", {"key": key}) from exc
    row = conn.execute("select * from topics where id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_dict(row)


@router.patch("/{key}")
def update_topic(request: Request, key: str, body: dict) -> dict:
    conn = _conn(request)
    row = conn.execute("select * from topics where key = ?", (key,)).fetchone()
    if row is None:
        raise not_found("方向")
    fields = {}
    if "label" in body:
        fields["label"] = body["label"]
    if "keywords" in body:
        fields["keywords"] = json.dumps(body["keywords"], ensure_ascii=False)
    if "weight" in body:
        fields["weight"] = float(body["weight"])
    if "enabled" in body:
        fields["enabled"] = 1 if body["enabled"] else 0
    if fields:
        assignments = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"update topics set {assignments} where key = ?", [*fields.values(), key])
        conn.commit()
    return _row_to_dict(conn.execute("select * from topics where key = ?", (key,)).fetchone())


@router.delete("/{key}", status_code=204)
def delete_topic(request: Request, key: str) -> None:
    conn = _conn(request)
    row = conn.execute("select id from topics where key = ?", (key,)).fetchone()
    if row is None:
        raise not_found("方向")
    conn.execute("update topics set enabled = 0 where key = ?", (key,))
    conn.commit()
