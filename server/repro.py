"""复现方案：缓存键 (paper_id, model)，与背景无关。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from ideasearch.llm import DeepSeek

from .fulltext import fetch_text
from .prompts import repro_messages, validate_repro

MAX_ATTEMPTS = 2


def get_cached(conn, paper_id: str, model: str) -> dict | None:
    row = conn.execute(
        "select evidence_json, estimate_json, plan_md from repro_plans "
        "where paper_id = ? and model = ?", (paper_id, model)).fetchone()
    if row is None:
        return None
    return {
        "evidence": json.loads(row["evidence_json"] or "{}"),
        "estimate": json.loads(row["estimate_json"] or "{}"),
        "planMd": row["plan_md"],
    }


def store(conn, paper_id: str, model: str, data: dict) -> None:
    conn.execute(
        "insert into repro_plans(id, paper_id, model, status, evidence_json, estimate_json, "
        "plan_md, created_at) values (?,?,?,?,?,?,?,?) "
        "on conflict(paper_id, model) do update set evidence_json = excluded.evidence_json, "
        "estimate_json = excluded.estimate_json, plan_md = excluded.plan_md, "
        "created_at = excluded.created_at",
        (uuid.uuid4().hex, paper_id, model, "succeeded",
         json.dumps({**data.get("evidence", {}), "likelihood": data.get("likelihood"),
                     "missing": data.get("missing", []),
                     "handoff_prompt": data.get("handoff_prompt", "")}, ensure_ascii=False),
         json.dumps(data.get("estimate", {}), ensure_ascii=False),
         str(data.get("plan_md", "")),
         datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    conn.commit()


def run_repro(conn, paper: dict, *, client=None, fetcher=fetch_text, api_key: str = "") -> dict:
    client = client or DeepSeek()
    text, _status = fetcher(paper["url"], api_key=api_key)
    problems: list[str] = ["未尝试"]
    for _ in range(MAX_ATTEMPTS):
        data = client.chat_json(repro_messages(paper, text))
        problems = validate_repro(data)
        if not problems:
            return data
    raise ValueError("复现方案未通过校验：" + "；".join(problems))
