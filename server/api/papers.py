"""论文级接口：深读与单篇详情。复现方案在 Task 9 接入。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from ..deepread import background_hash, get_cached, run_deep_read, store
from ..errors import ApiError, not_found
from ..repro import get_cached as get_cached_repro
from ..repro import run_repro
from ..repro import store as store_repro
from ..settings import SettingsStore, build_client

router = APIRouter(prefix="/papers", tags=["papers"])


def _settings(request: Request) -> SettingsStore:
    return SettingsStore(request.app.state.conn)


def _background(store_: SettingsStore) -> dict:
    return json.loads(store_.get_raw()["background_json"] or "{}")


@router.get("/{paper_id}")
def get_paper(request: Request, paper_id: str) -> dict:
    conn = request.app.state.conn
    row = conn.execute("select * from papers where id = ?", (paper_id,)).fetchone()
    if row is None:
        raise not_found("论文")
    settings = _settings(request)
    raw = settings.get_raw()
    bg_hash = background_hash(_background(settings))
    return {
        "id": row["id"],
        "externalId": row["external_id"],
        "url": row["url"],
        "title": row["title"],
        "authors": json.loads(row["authors"] or "[]"),
        "published": row["published"],
        "abstract": row["abstract"],
        "fulltextStatus": row["fulltext_status"],
        "deepRead": get_cached(conn, paper_id, bg_hash, raw["llm_model"]),
        "reproPlan": get_cached_repro(conn, paper_id, raw["llm_model"]),
    }


@router.post("/{paper_id}/deep-read", status_code=202)
def post_deep_read(request: Request, paper_id: str) -> dict:
    conn = request.app.state.conn
    runner = request.app.state.runner
    row = conn.execute("select * from papers where id = ?", (paper_id,)).fetchone()
    if row is None:
        raise not_found("论文")

    settings = _settings(request)
    if not settings.is_ready():
        raise ApiError(400, "NO_API_KEY", "未配置模型 API key")

    raw = settings.get_raw()
    background = _background(settings)
    bg_hash = background_hash(background)
    model = raw["llm_model"]

    if get_cached(conn, paper_id, bg_hash, model) is not None:
        job_id = runner.submit("deep_read", paper_id,
                               lambda ctx: ctx.set_progress(100, "命中缓存"))
        return {"jobId": job_id, "cached": True}

    paper = dict(row)

    def work(ctx) -> None:
        ctx.set_progress(5, "抓取全文")
        content = run_deep_read(conn, paper, background, client=build_client(raw),
                                api_key=raw["llm_api_key"])
        store(conn, paper_id, bg_hash, model, content)
        ctx.set_progress(100, "完成")

    return {"jobId": runner.submit("deep_read", paper_id, work), "cached": False}


@router.post("/{paper_id}/repro-plan", status_code=202)
def post_repro_plan(request: Request, paper_id: str) -> dict:
    conn = request.app.state.conn
    runner = request.app.state.runner
    row = conn.execute("select * from papers where id = ?", (paper_id,)).fetchone()
    if row is None:
        raise not_found("论文")

    settings = _settings(request)
    if not settings.is_ready():
        raise ApiError(400, "NO_API_KEY", "未配置模型 API key")

    raw = settings.get_raw()
    model = raw["llm_model"]

    if get_cached_repro(conn, paper_id, model) is not None:
        job_id = runner.submit("repro_plan", paper_id,
                               lambda ctx: ctx.set_progress(100, "命中缓存"))
        return {"jobId": job_id, "cached": True}

    paper = dict(row)

    def work(ctx) -> None:
        ctx.set_progress(5, "检索开源线索")
        plan = run_repro(conn, paper, client=build_client(raw), api_key=raw["llm_api_key"])
        store_repro(conn, paper_id, model, plan)
        ctx.set_progress(100, "完成")

    return {"jobId": runner.submit("repro_plan", paper_id, work), "cached": False}
