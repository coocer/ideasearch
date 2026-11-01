"""Prompt 与输出校验。

摘要部分（本节）；深读与复现方案在 Task 8/9 追加。
所有 prompt 共享一条纪律：只依据给定材料，不编造数据。
"""

from __future__ import annotations

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
