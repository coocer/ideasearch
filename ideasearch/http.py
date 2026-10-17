"""极简 HTTP 客户端（stdlib urllib），带重试与统一 UA。

设计原则：不引入第三方依赖，任何异常都收敛成 HttpError，
让上层采集器可以「单个源失败不影响整体」。

TLS 说明：默认严格校验证书。部分环境的根证书库缺少 arXiv 证书链的签发者
（表现为 CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate），
此时会**降级为不校验证书重试一次**，并把原因写进 WARNINGS 供报告披露。
设置环境变量 IDEASEARCH_STRICT_TLS=1 可关闭该降级。
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.request

USER_AGENT = "ideasearch/0.1 (+https://github.com/coocer/ideasearch)"

#: 采集过程中的非致命警告（如 TLS 降级），由 collect() 汇总进报告。
WARNINGS: list[str] = []

_STRICT_TLS = os.environ.get("IDEASEARCH_STRICT_TLS", "").strip().lower() in ("1", "true", "yes")
_CTX_STRICT = ssl.create_default_context()
_CTX_UNVERIFIED = ssl._create_unverified_context()


class HttpError(RuntimeError):
    """网络请求最终失败。"""


def _decode(raw: bytes, charset: str | None) -> str:
    for enc in filter(None, (charset, "utf-8", "gb18030")):
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def _fetch(
    url: str,
    *,
    data: bytes | None,
    headers: dict,
    timeout: float,
    verified: bool,
) -> tuple[bytes, str | None]:
    req = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity", **headers},
    )
    ctx = _CTX_STRICT if verified else _CTX_UNVERIFIED
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    with opener.open(req, timeout=timeout) as resp:
        return resp.read(), resp.headers.get_content_charset()


def _is_cert_error(exc: BaseException) -> bool:
    reason = getattr(exc, "reason", exc)
    return isinstance(reason, ssl.SSLCertVerificationError) or isinstance(exc, ssl.SSLCertVerificationError)


def _with_tls_fallback(url: str, **kwargs) -> tuple[bytes, str | None]:
    """先严格校验；仅当证书链不完整时降级重试一次并记录警告。"""
    try:
        return _fetch(url, verified=True, **kwargs)
    except urllib.error.URLError as exc:
        if _STRICT_TLS or not _is_cert_error(exc):
            raise
        host = url.split("/")[2] if url.count("/") >= 2 else url
        message = f"{host} 证书链无法验证（本机根证书库缺失签发者），已降级为不校验证书访问"
        if message not in WARNINGS:
            WARNINGS.append(message)
        return _fetch(url, verified=False, **kwargs)


def get_text(
    url: str,
    *,
    headers: dict | None = None,
    timeout: float = 45,
    retries: int = 3,
    backoff: float = 2.0,
) -> str:
    """GET 并返回文本，失败按指数退避重试。"""
    last: Exception | None = None
    for attempt in range(retries):
        try:
            raw, charset = _with_tls_fallback(
                url, data=None, headers=headers or {}, timeout=timeout
            )
            return _decode(raw, charset)
        except urllib.error.HTTPError as exc:
            last = exc
            if exc.code in (400, 401, 403, 404):
                raise HttpError(f"HTTP {exc.code} for {url}") from exc
        except Exception as exc:  # noqa: BLE001 - 网络层什么都可能抛
            last = exc
        if attempt + 1 < retries:
            time.sleep(backoff * (attempt + 1))
    raise HttpError(f"GET {url} failed after {retries} attempts: {last}")


def post_json(
    url: str,
    payload: dict,
    *,
    headers: dict | None = None,
    timeout: float = 180,
    retries: int = 2,
    backoff: float = 3.0,
) -> dict:
    """POST JSON 并解析 JSON 响应。"""
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    last: Exception | None = None
    for attempt in range(retries):
        try:
            raw, charset = _with_tls_fallback(url, data=body, headers=hdrs, timeout=timeout)
            return json.loads(_decode(raw, charset))
        except urllib.error.HTTPError as exc:
            last = exc
            detail = ""
            try:
                detail = exc.read().decode("utf-8", "replace")[:500]
            except Exception:  # noqa: BLE001
                pass
            if exc.code in (401, 403):
                raise HttpError(f"HTTP {exc.code} for {url}: {detail}") from exc
        except Exception as exc:  # noqa: BLE001
            last = exc
        if attempt + 1 < retries:
            time.sleep(backoff * (attempt + 1))
    raise HttpError(f"POST {url} failed after {retries} attempts: {last}")
