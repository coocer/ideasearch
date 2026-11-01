"""topic 权重必须真的影响选材（设计文档 十五.7）。

注意：`rank_papers` 会「每个方向先占一席」以保证多样性，所以当 limit <= 方向数时，
顺序由方向声明顺序决定，权重只影响分数、不影响先后。因此这里断言的是分数与
方向内的取舍，而不是顶层顺序。
"""

from ideasearch import rank
from ideasearch.config import Topic, load_config

import pytest


def _paper(pid, title):
    return {
        "id": pid,
        "source": "arXiv",
        "kind": "paper",
        "title": title,
        "abstract": "details here",
        "url": f"https://arxiv.org/abs/{pid}",
        "published": "2026-10-30",
        "authors": ["A"],
        "categories": ["cs.LG"],
        "comment": "",
    }


def _config(inference_weight, hardware_weight):
    cfg = load_config()
    cfg.topics = [
        Topic("inference", "推理优化", ["kv cache"], inference_weight),
        Topic("hardware", "硬件动态", ["hbm"], hardware_weight),
    ]
    return cfg


def test_score_is_scaled_by_topic_weight():
    item = _paper("a", "KV cache eviction study")
    assert rank.score(item, 2, 3.0) > rank.score(item, 2, 1.0)
    # 差值 = hits × 权重差 = 2 × (3-1)；时效项在两次调用间有微秒级漂移，用 approx
    assert rank.score(item, 2, 3.0) - rank.score(item, 2, 1.0) == pytest.approx(4.0, abs=1e-6)


def test_configured_weight_reaches_ranking():
    papers = [_paper("a", "KV cache eviction study"), _paper("b", "HBM bandwidth study")]
    picked = rank.rank_papers(papers, _config(5.0, 1.0), limit=2)
    by_topic = {p["topic_key"]: p["score"] for p in picked}
    assert by_topic["inference"] > by_topic["hardware"]


def test_swapping_weights_swaps_scores():
    papers = [_paper("a", "KV cache eviction study"), _paper("b", "HBM bandwidth study")]
    picked = rank.rank_papers(papers, _config(1.0, 5.0), limit=2)
    by_topic = {p["topic_key"]: p["score"] for p in picked}
    assert by_topic["hardware"] > by_topic["inference"]
