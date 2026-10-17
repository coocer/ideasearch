"""单元测试（stdlib unittest，无网络依赖）。

运行：python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ideasearch import rank, render  # noqa: E402
from ideasearch.collect import Collected  # noqa: E402
from ideasearch.config import Topic, load_config  # noqa: E402
from ideasearch.generate import build_report  # noqa: E402
from ideasearch.llm import DeepSeek  # noqa: E402
from ideasearch.sources import conferences, rss  # noqa: E402


def paper(**kw) -> dict:
    base = {
        "id": "2507.00001",
        "source": "arXiv",
        "kind": "paper",
        "title": "Sample Paper",
        "abstract": "We study KV cache quantization for inference serving.",
        "url": "https://arxiv.org/abs/2507.00001",
        "published": "2025-07-18",
        "authors": ["A"],
        "categories": ["cs.LG"],
        "comment": "",
    }
    base.update(kw)
    return base


class ConferenceTests(unittest.TestCase):
    def test_detect_venue_normalizes_case(self):
        self.assertEqual(conferences.detect_venue("Accepted by NeurIPS 2025"), "NeurIPS")
        self.assertEqual(conferences.detect_venue("to appear at ICML 2025"), "ICML")

    def test_detect_venue_requires_acceptance_wording(self):
        self.assertIsNone(conferences.detect_venue("We compare against NeurIPS baselines."))

    def test_display_venue_maps_known_names(self):
        self.assertEqual(conferences.display_venue("acm mm"), "ACM MM")
        self.assertEqual(conferences.display_venue("NEURIPS"), "NeurIPS")
        self.assertEqual(conferences.display_venue("USENIX ATC"), "USENIX ATC")

    def test_active_conferences_returns_window_shape(self):
        for conf in conferences.active_conferences():
            self.assertIn("start", conf)
            self.assertIn("end", conf)
            self.assertLessEqual(conf["start"], conf["end"])


class RankTests(unittest.TestCase):
    def setUp(self):
        self.topics = [
            Topic("inference", "推理优化", ["kv cache", "quantization", "serving"]),
            Topic("hardware", "硬件动态", ["hbm", "gpu"]),
        ]

    def test_dedupe_keeps_richer_duplicate(self):
        short = paper(title="KV Cache Quantization", abstract="short")
        long = paper(title="KV Cache Quantization!", abstract="x" * 500)
        kept = rank.dedupe([short, long])
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(kept[0]["abstract"]), 500)

    def test_assign_topic_matches_keywords(self):
        key, hits = rank.assign_topic(paper(title="HBM bandwidth for GPU clusters"), self.topics)
        self.assertEqual(key, "hardware")
        self.assertGreater(hits, 0)

    def test_assign_topic_falls_back_to_first_topic(self):
        key, hits = rank.assign_topic(paper(title="Unrelated", abstract="nothing"), self.topics)
        self.assertEqual(key, "inference")
        self.assertEqual(hits, 0)

    def test_rank_papers_respects_limit_and_covers_topics(self):
        config = load_config()
        items = [paper(id=f"p{i}", title=f"KV cache paper {i}") for i in range(6)]
        items.append(paper(id="h1", title="HBM4 GPU interconnect study"))
        picked = rank.rank_papers(items, config, limit=3)
        self.assertLessEqual(len(picked), 3)
        self.assertIn("topic", picked[0])
        self.assertIn("score", picked[0])


class RssTests(unittest.TestCase):
    RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>Hello &amp; World</title><link>https://x.test/a</link>
      <description>&lt;p&gt;body text&lt;/p&gt;</description>
      <pubDate>Fri, 18 Jul 2025 10:00:00 GMT</pubDate></item>
    </channel></rss>"""

    ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Atom Entry</title><link href="https://x.test/b"/>
      <summary>atom body</summary><published>2025-07-17T08:00:00Z</published></entry>
    </feed>"""

    def test_parse_rss2(self):
        items = rss.parse_feed(self.RSS, name="T", kind="industry", weight=1.0)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Hello & World")
        self.assertEqual(items[0]["abstract"], "body text")
        self.assertEqual(items[0]["published"], "2025-07-18")

    def test_parse_atom(self):
        items = rss.parse_feed(self.ATOM, name="T", kind="vendor", weight=1.0)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://x.test/b")
        self.assertEqual(items[0]["published"], "2025-07-17")


class RenderTests(unittest.TestCase):
    def _report(self) -> dict:
        return {
            "title": "周观察报告",
            "generated_at": "2025-07-20T10:00:00+08:00",
            "period": {"start": "2025-07-15", "end": "2025-07-20"},
            "overview": ["本期精读论文 1 篇。"],
            "model": "deepseek-chat",
            "conferences": [],
            "warnings": [],
            "papers": [
                {
                    "title": "Sample | Paper",
                    "url": "https://arxiv.org/abs/1",
                    "source": "arXiv",
                    "topic": "推理优化",
                    "published": "2025-07-18",
                    "authors": ["A"],
                    "one_line": "一句话",
                    "core_problem": "问题",
                    "technique": "手段",
                    "results": "效果",
                    "outlook": "启发",
                }
            ],
            "news": [],
        }

    def test_markdown_has_required_sections(self):
        md = render.render_markdown(self._report())
        for heading in ("## 一、本期概览", "## 二、汇总表", "## 三、重点解读"):
            self.assertIn(heading, md)
        self.assertIn("**核心解决的问题**", md)
        self.assertIn("**后续计划和启发**", md)

    def test_markdown_escapes_table_pipes(self):
        self.assertIn("Sample \\| Paper", render.render_markdown(self._report()))

    def test_html_escapes_markup(self):
        html = render.render_html(self._report())
        self.assertIn("<!DOCTYPE html>", html)
        self.assertNotIn("<script>", html)


class GenerateTests(unittest.TestCase):
    def _collected(self) -> Collected:
        return Collected(
            papers=[paper(venue="neurips", topic="推理优化")],
            news=[
                {
                    "id": "n1",
                    "source": "量子位",
                    "kind": "competitor",
                    "title": "竞品动态",
                    "abstract": "摘要",
                    "url": "https://x.test/n",
                    "published": "2025-07-17",
                    "weight": 1.2,
                }
            ],
            warnings=["某个源失败"],
            fetched_at="2025-07-20T10:00:00+08:00",
        )

    def test_build_report_without_key_degrades(self):
        client = DeepSeek(api_key="x")
        client.api_key = ""  # 强制走降级路径，避免联网
        report = build_report(self._collected(), load_config(), client, workers=1)
        self.assertTrue(report["degraded"])
        self.assertEqual(report["papers"][0]["venue"], "NeurIPS")  # 归一化生效
        self.assertEqual(report["papers"][0]["degraded"], True)
        self.assertTrue(any("降级" in line or "模型" in line for line in [report["model"]]))
        self.assertIn("某个源失败", report["warnings"])

    def test_overview_mentions_news_and_topics(self):
        client = DeepSeek(api_key="x")
        client.api_key = ""
        report = build_report(self._collected(), load_config(), client, workers=1)
        joined = " ".join(report["overview"])
        self.assertIn("推理优化", joined)
        self.assertIn("竞品", joined)


class HttpTests(unittest.TestCase):
    def test_decode_falls_back_to_gb18030(self):
        from ideasearch.http import _decode

        self.assertEqual(_decode("中文".encode("gb18030"), None), "中文")
        self.assertEqual(_decode("中文".encode("utf-8"), "utf-8"), "中文")


if __name__ == "__main__":
    unittest.main()
