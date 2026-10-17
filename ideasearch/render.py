"""渲染：Markdown 与单文件 HTML。"""

from __future__ import annotations

import html
from pathlib import Path


def _cell(text: str, limit: int = 60) -> str:
    text = " ".join((text or "").split()).replace("|", "\\|")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_markdown(report: dict) -> str:
    period = report.get("period") or {}
    span = f"{period.get('start') or '—'} ~ {period.get('end') or '—'}"
    papers, news = report.get("papers", []), report.get("news", [])

    out: list[str] = [f"# {report.get('title', '周观察报告')}", ""]
    out.append(f"> 周期：{span} ｜ 生成时间：{report.get('generated_at', '')} ｜ 模型：{report.get('model', '')}")
    out.append(">")
    out.append(f"> 精读论文 {len(papers)} 篇 ｜ 行业/竞品动态 {len(news)} 条")
    out.append("")

    if report.get("overview"):
        out += ["## 一、本期概览", ""]
        out += [f"- {line}" for line in report["overview"]]
        out.append("")

    out += ["## 二、汇总表", "", "| # | 方向 | 主题 | 一句话结论 | 来源 |", "|---|---|---|---|---|"]
    for idx, item in enumerate(papers, 1):
        out.append(
            f"| {idx} | {_cell(item.get('topic', ''), 12)} | {_cell(item.get('title', ''), 46)} "
            f"| {_cell(item.get('one_line', ''), 50)} | {item.get('source', '')} |"
        )
    out.append("")

    out += ["## 三、重点解读", ""]
    for idx, item in enumerate(papers, 1):
        venue = f" ｜ 录用：{item['venue']}" if item.get("venue") else ""
        out.append(f"### {idx}. {item.get('title', '')}")
        out.append("")
        out.append(
            f"- 方向：{item.get('topic', '')} ｜ 来源：{item.get('source', '')} "
            f"｜ 发布：{item.get('published', '')}{venue}"
        )
        if item.get("url"):
            out.append(f"- 原文：<{item['url']}>")
        if item.get("authors"):
            out.append(f"- 作者：{', '.join(item['authors'][:6])}")
        out.append("")
        for label, key in (
            ("核心解决的问题", "core_problem"),
            ("核心技术手段", "technique"),
            ("实际效果", "results"),
            ("后续计划和启发", "outlook"),
        ):
            out.append(f"**{label}**：{item.get(key, '') or '（缺）'}")
            out.append("")

    if news:
        out += ["## 四、竞品与行业动态", "", "| # | 来源 | 要点 |", "|---|---|---|"]
        for idx, item in enumerate(news, 1):
            out.append(f"| {idx} | {item.get('source', '')} | {_cell(item.get('one_line', ''), 60)} |")
        out.append("")
        for idx, item in enumerate(news, 1):
            out.append(f"**{idx}. {item.get('title', '')}**（{item.get('source', '')}，{item.get('published', '')}）")
            out.append("")
            out.append(item.get("detail", "") or item.get("one_line", ""))
            if item.get("url"):
                out.append("")
                out.append(f"<{item['url']}>")
            out.append("")

    if report.get("conferences"):
        out += ["## 五、顶会窗口", "", "| 会议 | 方向 | 会期 |", "|---|---|---|"]
        for conf in report["conferences"]:
            out.append(f"| {conf.get('name')} | {conf.get('area')} | {conf.get('start')} ~ {conf.get('end')} |")
        out.append("")

    if report.get("warnings"):
        out += ["## 附：采集告警", ""]
        out += [f"- {w}" for w in report["warnings"]]
        out.append("")

    return "\n".join(out).rstrip() + "\n"


_CSS = """
:root{--bg:#f7f8fa;--card:#fff;--fg:#1f2328;--muted:#656d76;--line:#d8dee4;--accent:#0b6bcb}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--card:#161b22;--fg:#e6edf3;--muted:#8b949e;--line:#30363d;--accent:#58a6ff}}
*{box-sizing:border-box}
body{margin:0;padding:32px 16px;background:var(--bg);color:var(--fg);
 font:16px/1.75 -apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
main{max-width:900px;margin:0 auto;background:var(--card);border:1px solid var(--line);
 border-radius:12px;padding:40px}
h1{font-size:28px;margin:0 0 8px}
h2{font-size:21px;margin:36px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}
h3{font-size:18px;margin:28px 0 8px}
.meta{color:var(--muted);font-size:14px;margin:0 0 4px}
table{border-collapse:collapse;width:100%;font-size:14px;margin:12px 0}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left;vertical-align:top}
th{background:rgba(127,127,127,.08)}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
dl{margin:8px 0}
dt{font-weight:600;margin-top:10px}
dd{margin:2px 0 0;color:var(--fg)}
.warn{color:var(--muted);font-size:13px}
li{margin:4px 0}
"""


def _esc(text: str | None) -> str:
    return html.escape(str(text or ""), quote=True)


def render_html(report: dict) -> str:
    period = report.get("period") or {}
    span = f"{period.get('start') or '—'} ~ {period.get('end') or '—'}"
    papers, news = report.get("papers", []), report.get("news", [])

    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="zh-CN"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{_esc(report.get('title', '周观察报告'))}</title>",
        f"<style>{_CSS}</style></head><body><main>",
        f"<h1>{_esc(report.get('title', '周观察报告'))}</h1>",
        f'<p class="meta">周期：{_esc(span)} ｜ 生成时间：{_esc(report.get("generated_at", ""))} '
        f'｜ 模型：{_esc(report.get("model", ""))}</p>',
        f'<p class="meta">精读论文 {len(papers)} 篇 ｜ 行业/竞品动态 {len(news)} 条</p>',
    ]

    if report.get("overview"):
        parts.append("<h2>一、本期概览</h2><ul>")
        parts += [f"<li>{_esc(line)}</li>" for line in report["overview"]]
        parts.append("</ul>")

    parts.append("<h2>二、汇总表</h2><table><thead><tr><th>#</th><th>方向</th><th>主题</th>"
                 "<th>一句话结论</th><th>来源</th></tr></thead><tbody>")
    for idx, item in enumerate(papers, 1):
        parts.append(
            f"<tr><td>{idx}</td><td>{_esc(item.get('topic'))}</td>"
            f"<td>{_esc(item.get('title'))}</td><td>{_esc(item.get('one_line'))}</td>"
            f"<td>{_esc(item.get('source'))}</td></tr>"
        )
    parts.append("</tbody></table>")

    parts.append("<h2>三、重点解读</h2>")
    for idx, item in enumerate(papers, 1):
        link = f' <a href="{_esc(item.get("url"))}" target="_blank" rel="noreferrer">原文</a>' if item.get("url") else ""
        venue = f" ｜ 录用：{_esc(item['venue'])}" if item.get("venue") else ""
        parts.append(f"<h3>{idx}. {_esc(item.get('title'))}{link}</h3>")
        parts.append(
            f'<p class="meta">方向：{_esc(item.get("topic"))} ｜ 来源：{_esc(item.get("source"))} '
            f'｜ 发布：{_esc(item.get("published"))}{venue}</p>'
        )
        parts.append("<dl>")
        for label, key in (
            ("核心解决的问题", "core_problem"),
            ("核心技术手段", "technique"),
            ("实际效果", "results"),
            ("后续计划和启发", "outlook"),
        ):
            parts.append(f"<dt>{label}</dt><dd>{_esc(item.get(key) or '（缺）')}</dd>")
        parts.append("</dl>")

    if news:
        parts.append("<h2>四、竞品与行业动态</h2><table><thead><tr><th>#</th><th>来源</th>"
                     "<th>要点</th></tr></thead><tbody>")
        for idx, item in enumerate(news, 1):
            parts.append(f"<tr><td>{idx}</td><td>{_esc(item.get('source'))}</td>"
                         f"<td>{_esc(item.get('one_line'))}</td></tr>")
        parts.append("</tbody></table>")
        for idx, item in enumerate(news, 1):
            link = f' <a href="{_esc(item.get("url"))}" target="_blank" rel="noreferrer">链接</a>' if item.get("url") else ""
            parts.append(f"<h3>{idx}. {_esc(item.get('title'))}{link}</h3>")
            parts.append(f'<p class="meta">{_esc(item.get("source"))} ｜ {_esc(item.get("published"))}</p>')
            parts.append(f"<p>{_esc(item.get('detail') or item.get('one_line'))}</p>")

    if report.get("conferences"):
        parts.append("<h2>五、顶会窗口</h2><table><thead><tr><th>会议</th><th>方向</th>"
                     "<th>会期</th></tr></thead><tbody>")
        for conf in report["conferences"]:
            parts.append(f"<tr><td>{_esc(conf.get('name'))}</td><td>{_esc(conf.get('area'))}</td>"
                         f"<td>{_esc(conf.get('start'))} ~ {_esc(conf.get('end'))}</td></tr>")
        parts.append("</tbody></table>")

    if report.get("warnings"):
        parts.append('<h2>附：采集告警</h2><ul class="warn">')
        parts += [f"<li>{_esc(w)}</li>" for w in report["warnings"]]
        parts.append("</ul>")

    parts.append("</main></body></html>")
    return "\n".join(parts)


def write_outputs(report: dict, out_dir: Path, stem: str) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{stem}.md"
    html_path = out_dir / f"{stem}.html"
    md_path.write_text(render_markdown(report), encoding="utf-8")
    html_path.write_text(render_html(report), encoding="utf-8")
    return {"markdown": md_path, "html": html_path}
