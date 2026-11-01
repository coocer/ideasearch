"""FastAPI 应用工厂。

只做装配：注册路由、挂载静态资源、把 db_path 放进 app.state。
业务逻辑一律留在 server/ 的其他模块里。
"""

from __future__ import annotations

from fastapi import FastAPI


def create_app(db_path: str) -> FastAPI:
    app = FastAPI(title="ideasearch", version="0.1.0")
    app.state.db_path = db_path

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
