"""Prompt 与输出校验。

摘要部分（本节）；深读与复现方案在 Task 8/9 追加。
所有 prompt 共享一条纪律：只依据给定材料，不编造数据。
"""

from __future__ import annotations

import re

SUMMARY_FIELDS = ("one_line", "core_problem", "technique", "results", "outlook")

BACKGROUND_LABELS = {
    "role": "角色",
    "current_work": "当前在做的系统",
    "bottlenecks": "现在的瓶颈",
    "stack": "技术栈与环境",
    "near_term_goals": "半年内目标",
    "non_interests": "明确不关心的方向",
}

SYSTEM_PROMPT = (
    "你是资深 AI 基础设施与算法研究员，为个人研究雷达撰写论文摘要。"
    "硬性要求：只依据给定材料，不得编造数据、不得虚构实验结果；"
    "使用简体中文，专有名词保留英文；输出必须是合法 JSON 对象，不要包代码块或解释文字。"
)


def _background_block(background: dict) -> str:
    lines = []
    for key, value in (background or {}).items():
        text = str(value or "").strip()
        if text:
            lines.append(f"- {BACKGROUND_LABELS.get(key, key)}：{text}")
    return "\n".join(lines) or "- （读者未填写背景）"


def summary_messages(paper: dict, target_words: int, background: dict) -> list[dict]:
    background_text = _background_block(background)
    title = paper.get("title", "")
    abstract = str(paper.get("abstract", ""))[:6000]
    user = f"""请为下面这篇论文写四段式摘要。

读者背景（用于判断"对他有什么用"，不要把这段原样复述）：
{background_text}

论文标题：{title}
摘要原文：
{abstract}

目标总字数约 {target_words} 字，按以下字段分配：
1. core_problem：核心解决的问题
2. technique：核心技术手段
3. results：实际效果
4. outlook：后续计划与启发

输出 JSON 对象，字段为：
{{
  "one_line": "一句话结论，不超过 80 字",
  "core_problem": "…",
  "technique": "…",
  "results": "…",
  "outlook": "…"
}}

硬约束：
- 实际效果若材料没有量化数据，就写「材料未给出量化结果」，不得编造数字
- 不使用「值得关注」「具有重要意义」「相关性强」这类空话
- 每个字段都写实质性内容，不要只写一句过渡语
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def validate_summary(data: dict) -> list[str]:
    """返回问题列表；空列表表示通过。"""
    problems: list[str] = []
    for field in SUMMARY_FIELDS:
        if not str(data.get(field) or "").strip():
            problems.append(f"缺少或为空：{field}")
    one_line = str(data.get("one_line") or "").strip()
    if len(one_line) > 80:
        problems.append(f"one_line 超过 80 字（当前 {len(one_line)}）")
    return problems


# ---------------- 深读（evidence-first，借鉴 dsh-deepread） ----------------

DEEPREAD_FIELDS = (
    "why_it_matters", "background", "what_they_did", "why_it_works",
    "limits", "value_for_you", "verdict", "jargon", "claims",
)

VAGUE_PHRASES = ("值得关注", "具有重要意义", "相关性强", "值得深入研究", "有一定价值")

_NUMBER = re.compile(r"\d")


def deepread_messages(paper: dict, fulltext: str, background: dict) -> list[dict]:
    status = paper.get("fulltext_status", "full")
    source_note = ("以下是论文全文摘录" if status == "full" else "以下只有摘要，没有拿到全文")
    body = (fulltext or str(paper.get("abstract", "")))[:12000]
    user = f"""请为这篇论文写一篇「理解向」深读：让没读过它的人能跟下来，并判断值不值得投入。

读者背景（value_for_you 必须点名这里的具体内容）：
{_background_block(background)}

论文标题：{paper.get('title', '')}
{source_note}：
{body}

输出 JSON，字段：
{{
  "why_it_matters": "一句话说清这篇干了什么、为什么难",
  "background": "读懂它需要的前置知识，补到没读过的人能跟上",
  "what_they_did": "方法，类比优先于公式",
  "why_it_works": "为什么这招有效（机理），不要复述步骤",
  "limits": "局限、适用边界、作者没说的代价",
  "value_for_you": "点名读者背景里的具体内容，说清能怎么用或用不上",
  "verdict": 1,
  "jargon": [["术语", "解释"]],
  "claims": [{{"text": "论断", "evidence": "证据", "location": "原文位置，如 §3.2"}}]
}}
verdict 取值：1=了解 2=关注 3=深入

纪律：
1. 论点 ≠ 主题：写作者的主张，不是复述标题
2. 任何含数字的论断，必须在 claims 里给出 evidence 与 location
3. 原文没有证据时写「原文未提供证据」，严禁编造
4. 区分四档：作者原意 / 原文事实与数据 / 合理推断 / 无法确认
5. 案例 ≠ 普遍证据，相关 ≠ 因果
6. 反注水：删掉不改变理解的句子不要写
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def validate_deepread(data: dict) -> list[str]:
    problems: list[str] = []
    for field in DEEPREAD_FIELDS:
        if field not in data:
            problems.append(f"缺少字段：{field}")

    for index, claim in enumerate(data.get("claims") or [], 1):
        text = str((claim or {}).get("text", ""))
        if _NUMBER.search(text):
            missing = []
            if not str(claim.get("evidence", "")).strip():
                missing.append("证据")
            if not str(claim.get("location", "")).strip():
                missing.append("原文位置")
            if missing:
                problems.append(f"第 {index} 条论断含数字，但缺少{'、'.join(missing)}")

    value = str(data.get("value_for_you") or "").strip()
    if len(value) < 10 or any(phrase in value for phrase in VAGUE_PHRASES):
        problems.append("value_for_you 过于笼统：必须点到背景里的具体内容，不能只写「相关」")

    return problems


# ---------------- 复现方案 ----------------

REPRO_FIELDS = ("evidence", "likelihood", "estimate", "missing", "plan_md", "handoff_prompt")
EVIDENCE_LEVELS = ("code_available", "partial", "none")
LIKELIHOODS = ("低", "中", "高")


def repro_messages(paper: dict, fulltext: str = "") -> list[dict]:
    body = (fulltext or str(paper.get("abstract", "")))[:12000]
    user = f"""请为这篇论文出一份「复现方案」，读者会把它交给 Claude / Codex 等 Agent 执行。

论文标题：{paper.get('title', '')}
原文（可能是摘要）：
{body}

输出 JSON，字段：
{{
  "evidence": {{"level": "none", "note": "元数据里有没有代码链接、数据集、权重"}},
  "likelihood": "中",
  "estimate": {{"token_range": [1200000, 2500000], "time_range_days": [3, 5], "assumptions": ["…"]}},
  "missing": ["缺哪些信息会让估值不准"],
  "plan_md": "复现步骤，可执行的那种",
  "handoff_prompt": "可直接投喂给执行者的完整提示词"
}}
evidence.level 只能取 code_available / partial / none；likelihood 只能取 低/中/高。

纪律：
- 有依据就引用（代码链接、数据集、指标）；没有依据就明说，不要编造数字
- token_range 表示用 AI 协作完成该 demo 的大致消耗，不是论文自身的训练成本
- 区间必须 lo <= hi；估不准的地方写进 missing，不要假装精确
"""
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def _is_range(value) -> bool:
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(x, (int, float)) for x in value)
            and value[0] <= value[1])


def validate_repro(data: dict) -> list[str]:
    problems: list[str] = []
    for field in REPRO_FIELDS:
        if field not in data:
            problems.append(f"缺少字段：{field}")

    evidence = data.get("evidence") or {}
    if isinstance(evidence, dict):
        if evidence.get("level") not in EVIDENCE_LEVELS:
            problems.append(f"evidence.level 必须是 {EVIDENCE_LEVELS} 之一")
    else:
        problems.append("evidence 必须是对象")

    if data.get("likelihood") not in LIKELIHOODS:
        problems.append(f"likelihood 必须是 {LIKELIHOODS} 之一")

    estimate = data.get("estimate") or {}
    if not _is_range(estimate.get("token_range")):
        problems.append("estimate.token_range 必须是递增的两元素区间")
    if not _is_range(estimate.get("time_range_days")):
        problems.append("estimate.time_range_days 必须是递增的两元素区间")

    if not isinstance(data.get("missing"), list) or not data.get("missing"):
        problems.append("missing 必须是非空列表")
    for field in ("plan_md", "handoff_prompt"):
        if not str(data.get(field) or "").strip():
            problems.append(f"{field} 不能为空")

    return problems
