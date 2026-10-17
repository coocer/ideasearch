"""把采集结果变成结构化周报：逐项调用 DeepSeek 提炼四段式解读。

规范（来自团队要求）：
- 先表格汇总，再逐项介绍；
- 每项 500~1000 字，覆盖「核心解决的问题 / 核心技术手段 / 实际效果 / 后续计划和启发」；
- 每期 5~10 篇论文，且要有竞品动态等非论文内容。
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

from .config import Config
from .llm import DeepSeek, LLMError
from .sources import conferences

SYSTEM_PROMPT = (
    "你是资深 AI 基础设施与算法研究员，负责为团队撰写《周观察报告》的技术解读。"
    "硬性要求：只依据给定材料，不臆造数据、不虚构实验结论；使用简体中文，"
    "专有名词与模型名保留英文；输出必须是合法 JSON 对象，不要包含 Markdown 代码块或任何解释文字。"
)

PAPER_TEMPLATE = """请阅读下面的论文信息，输出 JSON。

标题：{title}
发布时间：{published}
作者：{authors}
分类：{categories}
评论/录用信息：{comment}
摘要：
{abstract}

输出 JSON 字段（全部为中文，专有名词保留英文）：
{{
  "one_line": "一句话结论，不超过 40 字，用于汇总表",
  "core_problem": "核心解决的问题：背景、现有方案的瓶颈、这篇论文要打掉什么，150~250 字",
  "technique": "核心技术手段：方法、架构、关键设计取舍，200~300 字",
  "results": "实际效果：给出材料中出现的指标与 baseline 对比；若材料没有量化数据，就写「材料未给出量化结果」，严禁编造，120~200 字",
  "outlook": "后续计划和启发：对团队的落地价值、需要跟进的风险，120~200 字"
}}"""

NEWS_TEMPLATE = """下面是一条行业/竞品动态，请输出 JSON。

来源：{source}
标题：{title}
发布时间：{published}
摘要：
{abstract}

输出 JSON 字段（中文）：
{{
  "one_line": "一句话要点，不超过 40 字",
  "detail": "这条动态意味着什么：关键技术/产品变化、对竞品格局或我们技术选型的影响，100~200 字"
}}"""

_SENTENCE = re.compile(r"(?<=[。！？.!?])\s*")


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _sentences(text: str, count: int = 2) -> str:
    parts = [s.strip() for s in _SENTENCE.split(text or "") if s.strip()]
    return " ".join(parts[:count]) or _clip(text, 200)


def _fallback_paper(item: dict) -> dict:
    """无模型时的降级：抽取式，不编造。"""
    abstract = item.get("abstract", "")
    return {
        "one_line": _clip(_sentences(abstract, 1), 60),
        "core_problem": _clip(abstract, 400),
        "technique": "（未启用模型，未做提炼；请阅读原文摘要获取方法细节。）",
        "results": "（未启用模型，未做提炼。）",
        "outlook": "（未启用模型，未做提炼。）",
        "degraded": True,
    }


def _fallback_news(item: dict) -> dict:
    return {
        "one_line": _clip(_sentences(item.get("abstract", "") or item.get("title", ""), 1), 60),
        "detail": _clip(item.get("abstract", ""), 300),
        "degraded": True,
    }


def summarize_paper(client: DeepSeek, item: dict) -> dict:
    if not client.available:
        return _fallback_paper(item)
    prompt = PAPER_TEMPLATE.format(
        title=item.get("title", ""),
        published=item.get("published", ""),
        authors=", ".join(item.get("authors", [])[:8]) or "未提供",
        categories=", ".join(item.get("categories", [])[:5]) or "未提供",
        comment=item.get("comment") or "无",
        abstract=_clip(item.get("abstract", ""), 6000),
    )
    try:
        data = client.chat_json(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2000,
        )
    except LLMError:
        return _fallback_paper(item)
    return {
        "one_line": _clip(str(data.get("one_line", "")), 80) or _fallback_paper(item)["one_line"],
        "core_problem": str(data.get("core_problem", "")).strip(),
        "technique": str(data.get("technique", "")).strip(),
        "results": str(data.get("results", "")).strip(),
        "outlook": str(data.get("outlook", "")).strip(),
        "degraded": False,
    }


def summarize_news(client: DeepSeek, item: dict) -> dict:
    if not client.available:
        return _fallback_news(item)
    prompt = NEWS_TEMPLATE.format(
        source=item.get("source", ""),
        title=item.get("title", ""),
        published=item.get("published", ""),
        abstract=_clip(item.get("abstract", ""), 3000),
    )
    try:
        data = client.chat_json(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800,
        )
    except LLMError:
        return _fallback_news(item)
    return {
        "one_line": _clip(str(data.get("one_line", "")), 80) or _fallback_news(item)["one_line"],
        "detail": str(data.get("detail", "")).strip(),
        "degraded": False,
    }


def _period(papers: list[dict], news: list[dict]) -> dict:
    dates = [p.get("published", "") for p in papers + news if p.get("published")]
    dates = sorted(d for d in dates if len(d) >= 10)
    return {"start": dates[0] if dates else "", "end": dates[-1] if dates else ""}


def _overview(papers: list[dict], news: list[dict], config: Config) -> list[str]:
    """规则生成的本期概览，不依赖模型。"""
    lines = []
    topics: dict[str, int] = {}
    for item in papers:
        topics[item.get("topic", "其它")] = topics.get(item.get("topic", "其它"), 0) + 1
    if topics:
        detail = "、".join(f"{name} {count} 篇" for name, count in sorted(topics.items(), key=lambda kv: -kv[1]))
        lines.append(f"本期精读论文 {len(papers)} 篇，覆盖方向：{detail}。")
    competitors = [n for n in news if n.get("kind") == "competitor"]
    if news:
        sources = "、".join(sorted({n.get("source", "") for n in news}))
        extra = f"，其中竞品/大厂动态 {len(competitors)} 条" if competitors else ""
        lines.append(f"收录行业动态 {len(news)} 条（来源：{sources}）{extra}。")
    venues = sorted({p["venue"] for p in papers if p.get("venue")})
    if venues:
        lines.append(f"其中来自顶会录用（{'、'.join(venues)}）的论文已标注。")
    return lines


def build_report(collected, config: Config, client: DeepSeek | None = None, workers: int = 4) -> dict:
    client = client or DeepSeek()
    papers = collected.papers
    news = collected.news

    # 历史采集结果里的会议名可能未规范化，这里统一
    for item in papers:
        if item.get("venue"):
            item["venue"] = conferences.display_venue(item["venue"])

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        paper_futures = {pool.submit(summarize_paper, client, item): item for item in papers}
        news_futures = {pool.submit(summarize_news, client, item): item for item in news}
        for future in as_completed([*paper_futures, *news_futures]):
            item = paper_futures.get(future) or news_futures.get(future)
            try:
                item["summary"] = future.result()
            except Exception as exc:  # noqa: BLE001
                item["summary"] = _fallback_paper(item) if item.get("kind") == "paper" else _fallback_news(item)
                collected.warnings.append(f"摘要失败（{item.get('title', '')[:40]}）：{exc}")

    for item in papers + news:
        item.update(item.get("summary", {}))

    return {
        "title": config.title,
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "period": _period(papers, news),
        "overview": _overview(papers, news, config),
        "conferences": collected.conferences,
        "papers": papers,
        "news": news,
        "warnings": collected.warnings,
        "model": client.model if client.available else "未启用（降级为抽取式摘要）",
        "degraded": not client.available,
    }
