"""原文获取：DeepSeek Fetch → 自抓 HTML → 放弃并标 abstract_only（spec 十七.6）。"""

from __future__ import annotations

from ideasearch.http import get_text as default_get_text
from ideasearch.http import post_json as default_post_json

FETCH_ENDPOINT = "https://api.deepseek.com/v1/tools/fetch"


def _html_url(url: str) -> str:
    """arXiv 的 abs 页没有正文，换成 html 版再试。"""
    return url.replace("/abs/", "/html/") if "/abs/" in url else url


def fetch_text(url: str, *, get_text=None, post_json=None, api_key: str = "") -> tuple[str, str]:
    """返回 (正文, 状态)。状态只有 full / abstract_only 两种。"""
    get_text = get_text or default_get_text
    post_json = post_json or default_post_json
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        data = post_json(FETCH_ENDPOINT, {"url": url}, headers=headers)
        content = str((data or {}).get("content") or "")
        if content.strip():
            return content, "full"
    except Exception:  # noqa: BLE001 - 降级路径，任何失败都继续往下试
        pass

    try:
        text = get_text(_html_url(url))
        if text.strip():
            return text, "full"
    except Exception:  # noqa: BLE001
        pass

    return "", "abstract_only"
