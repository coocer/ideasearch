"""深读的缓存与编排。

缓存键 = (paper_id, background_hash, model)：背景一改，旧深读必须失效，
否则会拿旧背景给你讲价值（spec 十五.3）。
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

from ideasearch.llm import DeepSeek

from .fulltext import fetch_text
from .prompts import deepread_messages, validate_deepread

MAX_ATTEMPTS = 2


def background_hash(background: dict | None) -> str:
    payload = json.dumps(background or {}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_cached(conn, paper_id: str, bg_hash: str, model: str) -> dict | None:
    row = conn.execute(
        "select content_json from deep_reads where paper_id = ? and background_hash = ? and model = ?",
        (paper_id, bg_hash, model),
    ).fetchone()
    return json.loads(row["content_json"]) if row else None


def store(conn, paper_id: str, bg_hash: str, model: str, content: dict, tokens: int = 0) -> None:
    conn.execute(
        "insert into deep_reads(id, paper_id, background_hash, model, status, content_json, "
        "tokens, created_at) values (?,?,?,?,?,?,?,?) "
        "on conflict(paper_id, background_hash, model) do update set "
        "content_json = excluded.content_json, tokens = excluded.tokens, "
        "created_at = excluded.created_at",
        (uuid.uuid4().hex, paper_id, bg_hash, model, "succeeded",
         json.dumps(content, ensure_ascii=False), int(tokens),
         datetime.now(timezone.utc).isoformat(timespec="seconds")),
    )
    conn.commit()


def run_deep_read(conn, paper, background: dict, *, client=None, fetcher=fetch_text,
                  api_key: str = "") -> dict:
    """产出深读内容；调用方负责缓存读写与状态落库。"""
    client = client or DeepSeek()
    text, status = fetcher(paper["url"], api_key=api_key)
    base = dict(paper)
    base["fulltext"] = text
    base["fulltext_status"] = status

    problems: list[str] = ["未尝试"]
    for _ in range(MAX_ATTEMPTS):
        data = client.chat_json(deepread_messages(base, text, background))
        problems = validate_deepread(data)
        if not problems:
            data["fulltext_status"] = status
            return data
    raise ValueError("深读未通过校验：" + "；".join(problems))
