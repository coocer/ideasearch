"""一期生成编排：采集 → 排序 → 逐篇摘要 → 落库。

只编排，不拼 SQL 之外的业务细节；单篇失败不拖垮整期，但成功篇数不足整期判失败。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

from ideasearch import rank
from ideasearch.collect import collect as default_collect
from ideasearch.llm import DeepSeek

from .budget import per_paper_words
from .search import collect_search
from .prompts import summary_messages, validate_summary

MAX_ATTEMPTS = 3
NEWS_LIMIT = 6


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _uid() -> str:
    return uuid.uuid4().hex


def _upsert_paper(conn, item: dict, external_id: str) -> str:
    """papers 全局唯一：同一篇论文跨期复用同一行（spec 十五.3）。"""
    conn.execute(
        "insert into papers(id, external_id, url, title, authors, published, abstract, fetched_at) "
        "values (?,?,?,?,?,?,?,?) "
        "on conflict(external_id) do update set url = excluded.url, title = excluded.title, "
        "authors = excluded.authors, published = excluded.published, "
        "abstract = excluded.abstract, fetched_at = excluded.fetched_at",
        (_uid(), external_id, item.get("url", ""), item.get("title", ""),
         json.dumps(item.get("authors", []), ensure_ascii=False),
         item.get("published", ""), item.get("abstract", ""), _now()),
    )
    row = conn.execute("select id from papers where external_id = ?", (external_id,)).fetchone()
    return row["id"]


def _news_messages(item: dict) -> list[dict]:
    return [
        {"role": "system", "content": "你为个人研究雷达撰写行业动态要点。只依据给定材料，不编造。输出合法 JSON。"},
        {"role": "user", "content": (
            "下面是一条行业/竞品动态，输出 JSON。\n"
            f"来源：{item.get('source', '')}\n标题：{item.get('title', '')}\n"
            f"摘要：{str(item.get('abstract', ''))[:2000]}\n\n"
            '字段：{"one_line": "不超过 40 字", "detail": "100~200 字，说明这条动态意味着什么"}'
        )},
    ]


def generate_issue(conn, cfg, ctx, target_words: int, *, collector=None,
                   client=None, background: dict | None = None) -> str:
    collector = collector or default_collect
    client = client or DeepSeek()
    if not getattr(client, "available", False):
        raise ValueError("未配置模型 API key，无法生成")
    background = background or {}

    ctx.set_progress(2, "正在采集论文与动态")
    result = collector(cfg)
    ctx.set_progress(35, "采集完成，检索方向关键词")

    # 只开搜索源也要能出内容：把检索结果并进动态池
    search_cfg = (cfg.raw or {}).get("search") or {}
    api_key = getattr(client, "api_key", "") or ""
    if search_cfg.get("enabled") and api_key:
        result.news.extend(collect_search(
            list(search_cfg.get("queries") or []),
            api_key=api_key,
            base_url=getattr(client, "base_url", "https://api.deepseek.com"),
            count=int(search_cfg.get("count", 8)),
            warnings=result.warnings,
        ))

    papers = rank.rank_papers(result.papers, cfg)
    news = rank.rank_news(result.news, cfg, limit=NEWS_LIMIT)
    ctx.set_progress(45, f"选出 {len(papers)} 篇，开始生成摘要")
    words = per_paper_words(target_words, len(papers), len(news))

    issue_id = _uid()
    window_days = int(cfg.arxiv.get("days_back", 7) or 7)
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=window_days)
    snapshot = {
        "topics": [{"key": t.key, "label": t.label, "weight": t.weight} for t in cfg.topics],
        "feeds": [{"name": f.name, "kind": f.kind, "weight": f.weight} for f in cfg.feeds],
        "background": background,
        "window_days": window_days,
    }
    conn.execute(
        "insert into issues(id, title, created_at, window_days, window_start, window_end, "
        "config_snapshot, target_words, status, model) values (?,?,?,?,?,?,?,?,?,?)",
        (issue_id, cfg.title, _now(), window_days, start.isoformat(), today.isoformat(),
         json.dumps(snapshot, ensure_ascii=False), int(target_words), "running",
         getattr(client, "model", "")),
    )
    conn.commit()

    ok_count = 0
    total = max(1, len(papers))
    for index, item in enumerate(papers, 1):
        external_id = str(item.get("external_id") or item.get("id") or _uid())
        summary: dict | None = None
        last_problems: list[str] = ["未尝试"]
        for _ in range(MAX_ATTEMPTS):
            try:
                data = client.chat_json(summary_messages(item, words, background))
                # 模型可能返回合法但非对象的 JSON（数组/字符串），必须先挡住，
                # 否则异常会穿出循环、整期永远停在 running（评审 Important）。
                if not isinstance(data, dict):
                    last_problems = ["模型未返回 JSON 对象"]
                    continue
                last_problems = validate_summary(data)
            except Exception as exc:  # noqa: BLE001
                last_problems = [str(exc)]
                continue
            if not last_problems:
                summary = data
                break

        paper_id = _upsert_paper(conn, item, external_id)
        status = "ok" if summary else "failed"
        ok_count += 1 if summary else 0
        conn.execute(
            "insert or replace into issue_papers(issue_id, paper_id, topic_key, score, "
            "selected_rank, one_line, summary_json, summary_status) values (?,?,?,?,?,?,?,?)",
            (issue_id, paper_id, item.get("topic_key", ""), float(item.get("score", 0)),
             index, (summary or {}).get("one_line", ""),
             json.dumps(summary or {}, ensure_ascii=False), status),
        )
        conn.commit()
        ctx.set_progress(45 + int(index / total * 50), f"生成 {index}/{len(papers)} 篇摘要")

    for item in news:
        one_line, detail = item.get("title", ""), ""
        try:
            data = client.chat_json(_news_messages(item))
            one_line = data.get("one_line") or one_line
            detail = data.get("detail") or ""
        except Exception:  # noqa: BLE001 - 动态失败降级为标题，不阻塞整期
            pass
        conn.execute(
            "insert or replace into news(id, issue_id, source, kind, title, url, published, "
            "one_line, detail) values (?,?,?,?,?,?,?,?,?)",
            (_uid(), issue_id, item.get("source", ""), item.get("kind", "industry"),
             item.get("title", ""), item.get("url", ""), item.get("published", ""),
             one_line, detail),
        )

    final_status = "succeeded" if ok_count >= cfg.min_papers else "failed"
    error = None
    if final_status == "failed":
        error = (f"成功摘要 {ok_count} 篇，少于要求的 {cfg.min_papers} 篇")
        if result.warnings:
            error += "；采集告警：" + "；".join(result.warnings[:3])
    conn.execute("update issues set status = ?, error = ? where id = ?",
                 (final_status, error, issue_id))
    ctx.set_progress(100, "完成")
    conn.commit()
    return issue_id
