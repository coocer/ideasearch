from server.budget import per_paper_words


def test_splits_target_across_papers():
    assert per_paper_words(9000, 6, 4) == (9000 - 800) // 6


def test_never_below_floor():
    assert per_paper_words(2000, 10, 10) >= 200


def test_single_paper_takes_most_of_budget():
    assert per_paper_words(9000, 1, 0) == 9000
