"""本地启动入口：uvicorn 只监听回环地址（spec 三：仅本机）。"""

from __future__ import annotations

from pathlib import Path

import uvicorn

from .app import create_app

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    db_path = ROOT / "ideasearch.db"
    uvicorn.run(create_app(str(db_path)), host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
