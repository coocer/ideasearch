"""配置接口。没有它，全新克隆永远无法配置 key（评审 Critical）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from ..settings import SettingsStore, build_client

router = APIRouter(prefix="/settings", tags=["settings"])


def _store(request: Request) -> SettingsStore:
    return SettingsStore(request.app.state.conn)


@router.get("")
def read_settings(request: Request) -> dict:
    return _store(request).get()


@router.put("")
def write_settings(request: Request, body: dict) -> dict:
    payload = dict(body)
    background = payload.get("background_json")
    if isinstance(background, dict):
        payload["background_json"] = json.dumps(background, ensure_ascii=False)
    return _store(request).update(payload)


@router.post("/test")
def test_settings(request: Request) -> dict:
    """只校验配置是否齐全，不发网络请求（连通性由第一次真实调用暴露）。"""
    store = _store(request)
    raw = store.get_raw()
    return {
        "ok": store.is_ready(),
        "model": raw["llm_model"],
        "baseUrl": raw["llm_base_url"],
        "hasKey": bool(str(raw["llm_api_key"]).strip()),
    }


def client_for(raw: dict):
    """路由层统一用它构造客户端，确保用的是库里的配置。"""
    return build_client(raw)
