"""配置接口。没有它，全新克隆永远无法配置 key（评审 Critical）。"""

from __future__ import annotations

import json

from fastapi import APIRouter, Request

from ..seed import seed_defaults
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
    result = _store(request).update(payload)
    # 首次保存时导入默认方向与数据源，否则空库无法采集
    seed_defaults(request.app.state.conn)
    return result


@router.post("/test")
def test_settings(request: Request, body: dict | None = None) -> dict:
    """用当前表单值真的发一次最小请求，验证 key 有效（而不是只看有没有填）。"""
    store = _store(request)
    raw = dict(store.get_raw())
    body = body or {}
    if body.get("baseUrl"):
        raw["llm_base_url"] = str(body["baseUrl"])
    if body.get("model"):
        raw["llm_model"] = str(body["model"])
    key = str(body.get("apiKey") or "").strip()
    if key and key != "sk-***":
        raw["llm_api_key"] = key

    if not str(raw["llm_api_key"]).strip():
        return {"ok": False, "message": "还没有填写 API Key"}

    client = build_client(raw)
    try:
        client.chat([{"role": "user", "content": "ping"}], max_tokens=8)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "message": f"连接失败：{exc}"}
    return {"ok": True, "message": "连接正常，模型可用", "model": raw["llm_model"]}


def client_for(raw: dict):
    """路由层统一用它构造客户端，确保用的是库里的配置。"""
    return build_client(raw)
