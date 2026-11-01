"""测试公共夹具。

环境说明：本机沙箱下「运行时新建的嵌套目录」无法被枚举，
因此测试不使用 pytest 的 `tmp_path`，改用仓库内固定目录下的唯一文件名。
见 .superpowers/sdd/.../progress.md 的 Ruling 2。
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from server.app import create_app

ARTIFACTS = Path(__file__).resolve().parent / "_artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)


@pytest.fixture()
def db_file() -> Path:
    """本次测试独占的数据库文件路径（父目录已存在，不新建目录）。"""
    return ARTIFACTS / f"{uuid.uuid4().hex}.db"


@pytest.fixture()
def client(db_file) -> TestClient:
    with TestClient(create_app(str(db_file))) as c:
        yield c
