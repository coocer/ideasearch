"""命令行入口。

  python -m ideasearch collect              # 只采集，落盘 data/collected-*.json
  python -m ideasearch generate --input ...  # 从采集结果生成报告
  python -m ideasearch run                   # 采集 + 生成（一条龙）
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from . import __version__, collect as collector, generate, rank, render
from .config import ROOT, load_config, load_dotenv
from .llm import DeepSeek


def _stem(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M')}"


def _init(args) -> None:
    load_dotenv(ROOT / ".env")


def cmd_collect(args) -> int:
    config = load_config(Path(args.config) if args.config else None)
    result = collector.collect(config)
    path = collector.save(result, config.root / "data" / f"{_stem('collected')}.json")
    print(f"采集完成：论文 {len(result.papers)} 篇，动态 {len(result.news)} 条")
    for warning in result.warnings:
        print(f"  ! {warning}")
    print(f"已保存：{path}")
    return 0


def _build(args, result) -> dict:
    config = load_config(Path(args.config) if args.config else None)
    result.papers = rank.rank_papers(result.papers, config, args.limit)
    result.news = rank.rank_news(result.news, config, args.news)
    client = DeepSeek()
    if args.no_llm:
        client.api_key = ""
    report = generate.build_report(result, config, client, workers=args.workers)
    out_dir = config.output_dir
    stem = _stem("report")
    paths = render.write_outputs(report, out_dir, stem)
    json_path = out_dir / f"{stem}.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"报告已生成：{len(report['papers'])} 篇论文 / {len(report['news'])} 条动态")
    print(f"  Markdown: {paths['markdown']}")
    print(f"  HTML    : {paths['html']}")
    print(f"  JSON    : {json_path}")
    if report.get("degraded"):
        print("  ! 未启用 DeepSeek（缺少 DEEPSEEK_API_KEY 或 --no-llm），已降级为抽取式摘要")
    return report


def cmd_generate(args) -> int:
    _init(args)
    if not args.input:
        result = collector.load(max(Path("data").glob("collected-*.json"), key=lambda p: p.stat().st_mtime))
    else:
        result = collector.load(Path(args.input))
    _build(args, result)
    return 0


def cmd_run(args) -> int:
    _init(args)
    config = load_config(Path(args.config) if args.config else None)
    if args.input:
        result = collector.load(Path(args.input))
    else:
        result = collector.collect(config)
        collector.save(result, config.root / "data" / f"{_stem('collected')}.json")
    _build(args, result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ideasearch", description="周观察报告生成器")
    parser.add_argument("--version", action="version", version=f"ideasearch {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--config", help="config.toml 路径")
        p.add_argument("--limit", type=int, default=None, help="精读论文数（默认取配置 max_papers）")
        p.add_argument("--news", type=int, default=8, help="竞品/行业动态条数")
        p.add_argument("--workers", type=int, default=4, help="并发调用模型数")
        p.add_argument("--no-llm", action="store_true", help="不调用模型，仅抽取式摘要")

    p_collect = sub.add_parser("collect", help="只采集数据")
    p_collect.add_argument("--config", help="config.toml 路径")
    p_collect.set_defaults(func=cmd_collect)

    p_generate = sub.add_parser("generate", help="从已采集数据生成报告")
    p_generate.add_argument("--input", help="collected JSON 路径")
    common(p_generate)
    p_generate.set_defaults(func=cmd_generate)

    p_run = sub.add_parser("run", help="采集 + 生成")
    p_run.add_argument("--input", help="跳过采集，直接用已有 collected JSON")
    common(p_run)
    p_run.set_defaults(func=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "command", "") != "collect":
        _init(args)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
