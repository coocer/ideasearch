"""FastAPI 应用工厂。

只做装配：生命周期内建库连接、注册路由与错误信封、把 db_path 放进 app.state。
业务逻辑一律留在 server/ 的其他模块里。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api import issues, jobs, papers, sources, topics
from .api import settings as settings_api
from .db import connect, init_schema
from .errors import ApiError, api_error_handler
from .jobs import JobRunner


def create_app(db_path: str, spa_dir: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = connect(db_path)
        init_schema(conn)
        app.state.conn = conn
        runner = JobRunner(conn)
        runner.start()
        app.state.runner = runner
        try:
            yield
        finally:
            runner.stop()
            conn.close()

    app = FastAPI(title="ideasearch", version="0.1.0", lifespan=lifespan)
    app.state.db_path = db_path
    app.add_exception_handler(ApiError, api_error_handler)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(topics.router, prefix="/api/v1")
    app.include_router(sources.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(papers.router, prefix="/api/v1")
    app.include_router(issues.router, prefix="/api/v1")
    app.include_router(settings_api.router, prefix="/api/v1")

    dist = Path(spa_dir) if spa_dir else Path(__file__).resolve().parent.parent / "web" / "dist"
    if (dist / "index.html").is_file():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        root = dist.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            """深链接回落 index.html；API 路径绝不吞。"""
            if full_path == "api" or full_path.startswith("api/"):
                raise HTTPException(status_code=404)
            if full_path:
                candidate = (root / full_path).resolve()
                if candidate.is_file() and root in candidate.parents:
                    return FileResponse(candidate)
            return FileResponse(root / "index.html")

    return app
