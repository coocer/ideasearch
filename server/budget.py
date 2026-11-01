"""字数预算：一期总量反推每篇字数（spec 十.1 / 十五.3）。"""

from __future__ import annotations

#: 每条行业动态按固定字数计入预算
NEWS_WORDS = 200
#: 单篇摘要下限，避免篇数过多时把每篇压成一句
FLOOR = 200


def per_paper_words(
    target_words: int,
    paper_count: int,
    news_count: int,
    words_per_news: int = NEWS_WORDS,
) -> int:
    """把一期总字数扣掉动态占用后均摊到论文。"""
    if paper_count <= 0:
        return 0
    remaining = max(0, int(target_words) - int(news_count) * int(words_per_news))
    return max(FLOOR, remaining // int(paper_count))
