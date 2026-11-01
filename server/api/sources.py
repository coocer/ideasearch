"""数据源 CRUD：arxiv / rss / search 三类，删除是软删。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from ..errors import ApiError, not_found

router = APIRouter(prefix="/sources", tags=["sources"])

KINDS = {"arxiv", "rss", "search"}


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "kind": row["kind"],
        "name": row["name"],
        "url": row["url"],
        "config": json.loads(row["config"] or "{}"),
        "weight": row["weight"],
        "enabled": bool(row["enabled"]),
    }


def _conn(request: Request):
    return request.app.state.conn


@router.get("")
def list_sources(request: Request) -> dict:
    rows = _conn(request).execute("select * from sources order by id").fetchall()
    items = [_row_to_dict(r) for r in rows]
    return {"items": items, "total": len(items), "page": 1, "pageSize": len(items)}


@router.post("", status_code=201)
def create_source(request: Request, body: dict) -> dict:
    kind = str(body.get("kind", "")).strip()
    if kind not in KINDS:
        raise ApiError(400, "INVALID_KIND", f"kind 必须是 {sorted(KINDS)} 之一")
    conn = _conn(request)
    cur = conn.execute(
        "insert into sources(kind, name, url, config, weight, enabled) values (?,?,?,?,?,?)",
        (kind, body.get("name", ""), body.get("url", ""),
         json.dumps(body.get("config", {}), ensure_ascii=False),
         float(body.get("weight", 1)), 1 if body.get("enabled", True) else 0),
    )
    conn.commit()
    row = conn.execute("select * from sources where id = ?", (cur.lastrowid,)).fetchone()
    return _row_to_dict(row)


@router.patch("/{source_id}")
def update_source(request: Request, source_id: int, body: dict) -> dict:
    conn = _conn(request)
    row = conn.execute("select * from sources where id = ?", (source_id,)).fetchone()
    if row is None:
        raise not_found("数据源")
    fields = {}
    for name in ("name", "url"):
        if name in body:
            fields[name] = body[name]
    if "config" in body:
        fields["config"] = json.dumps(body["config"], ensure_ascii=False)
    if "weight" in body:
        fields["weight"] = float(body["weight"])
    if "enabled" in body:
        fields["enabled"] = 1 if body["enabled"] else 0
    if fields:
        assignments = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"update sources set {assignments} where id = ?",
                     [*fields.values(), source_id])
        conn.commit()
    return _row_to_dict(conn.execute("select * from sources where id = ?", (source_id,)).fetchone())


@router.delete("/{source_id}", status_code=204)
def delete_source(request: Request, source_id: int) -> None:
    conn = _conn(request)
    row = conn.execute("select id from sources where id = ?", (source_id,)).fetchone()
    if row is None:
        raise not_found("数据源")
    conn.execute("update sources set enabled = 0 where id = ?", (source_id,))
    conn.commit()
