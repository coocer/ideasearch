"""一期文章的生成、查询、删除与 Markdown 导出。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from ..errors import ApiError, not_found
from ..pipeline import generate_issue
from ..settings import SettingsStore

router = APIRouter(prefix="/issues", tags=["issues"])


def _escape(text: str) -> str:
    """Markdown 表格里 `|` 必须转义，否则整行错位。"""
    return str(text or "").replace("|", "\\|")


def _conn(request: Request):
    return request.app.state.conn


@router.get("")
def list_issues(request: Request) -> dict:
    rows = _conn(request).execute(
        "select * from issues order by created_at desc").fetchall()
    items = [{
        "id": r["id"], "title": r["title"], "createdAt": r["created_at"],
        "windowDays": r["window_days"], "status": r["status"],
        "targetWords": r["target_words"],
    } for r in rows]
    return {"items": items, "total": len(items), "page": 1, "pageSize": len(items)}


@router.post("", status_code=202)
def create_issue(request: Request) -> dict:
    conn = _conn(request)
    settings = SettingsStore(conn)
    if not settings.is_ready():
        raise ApiError(400, "NO_API_KEY", "未配置模型 API key")
    cfg = settings.to_config()
    background = json.loads(settings.get_raw()["background_json"] or "{}")
    target_words = settings.target_words()

    def work(ctx) -> None:
        generate_issue(conn, cfg, ctx, target_words, background=background)

    job_id = request.app.state.runner.submit("issue", "", work)
    return {"jobId": job_id}


@router.get("/{issue_id}")
def get_issue(request: Request, issue_id: str) -> dict:
    conn = _conn(request)
    issue = conn.execute("select * from issues where id = ?", (issue_id,)).fetchone()
    if issue is None:
        raise not_found("文章")

    papers = conn.execute(
        "select p.*, ip.summary_json, ip.summary_status, ip.topic_key, ip.one_line "
        "from issue_papers ip join papers p on p.id = ip.paper_id "
        "where ip.issue_id = ? order by ip.selected_rank", (issue_id,)).fetchall()
    news = conn.execute("select * from news where issue_id = ?", (issue_id,)).fetchall()

    return {
        "id": issue["id"],
        "title": issue["title"],
        "createdAt": issue["created_at"],
        "status": issue["status"],
        "targetWords": issue["target_words"],
        "papers": [{
            "id": p["id"],
            "title": p["title"],
            "url": p["url"],
            "topicKey": p["topic_key"],
            "oneLine": p["one_line"],
            "summary": json.loads(p["summary_json"] or "{}"),
            "status": p["summary_status"],
        } for p in papers if p["summary_status"] == "ok"],
        "news": [{
            "title": n["title"], "source": n["source"],
            "oneLine": n["one_line"], "detail": n["detail"], "url": n["url"],
        } for n in news],
    }


@router.delete("/{issue_id}", status_code=204)
def delete_issue(request: Request, issue_id: str) -> None:
    conn = _conn(request)
    if conn.execute("select id from issues where id = ?", (issue_id,)).fetchone() is None:
        raise not_found("文章")
    conn.execute("delete from issues where id = ?", (issue_id,))
    conn.commit()


@router.get("/{issue_id}/export", response_class=PlainTextResponse)
def export_issue(request: Request, issue_id: str) -> str:
    conn = _conn(request)
    issue = conn.execute("select * from issues where id = ?", (issue_id,)).fetchone()
    if issue is None:
        raise not_found("文章")

    papers = conn.execute(
        "select p.*, ip.summary_json, ip.topic_key from issue_papers ip "
        "join papers p on p.id = ip.paper_id where ip.issue_id = ? "
        "and ip.summary_status = 'ok' order by ip.selected_rank", (issue_id,)).fetchall()
    news = conn.execute("select * from news where issue_id = ?", (issue_id,)).fetchall()

    lines = [f"# {issue['title']}", ""]
    lines.append(f"> 周期：{issue['window_start']} ~ {issue['window_end']}"
                 f" ｜ 目标字数：{issue['target_words']}")
    lines.append("")

    if papers:
        lines += ["| # | 方向 | 主题 | 一句话 |", "|---|---|---|---|"]
        for index, row in enumerate(papers, 1):
            summary = json.loads(row["summary_json"] or "{}")
            lines.append(
                f"| {index} | {_escape(row['topic_key'])} | {_escape(row['title'])} "
                f"| {_escape(summary.get('one_line', ''))} |")
        lines.append("")

        for index, row in enumerate(papers, 1):
            summary = json.loads(row["summary_json"] or "{}")
            lines.append(f"### {index}. {_escape(row['title'])}")
            lines.append("")
            for label, key in (("核心解决的问题", "core_problem"),
                               ("核心技术手段", "technique"),
                               ("实际效果", "results"),
                               ("后续计划与启发", "outlook")):
                lines.append(f"**{label}**：{summary.get(key, '')}")
                lines.append("")

    deep_rows = conn.execute(
        "select d.content_json, p.title from deep_reads d join papers p on p.id = d.paper_id "
        "join issue_papers ip on ip.paper_id = p.id where ip.issue_id = ?", (issue_id,)).fetchall()
    if deep_rows:
        lines += ["## 深读", ""]
        for row in deep_rows:
            content = json.loads(row["content_json"] or "{}")
            lines.append(f"### {_escape(row['title'])}")
            lines.append("")
            lines.append(str(content.get("why_it_matters", "")))
            lines.append("")
            lines.append(str(content.get("value_for_you", "")))
            lines.append("")

    if news:
        lines += ["## 行业与竞品动态", "", "| # | 来源 | 要点 |", "|---|---|---|"]
        for index, row in enumerate(news, 1):
            lines.append(f"| {index} | {_escape(row['source'])} | {_escape(row['one_line'])} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
