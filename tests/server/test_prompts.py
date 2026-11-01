from server.prompts import summary_messages, validate_summary

BG = {
    "role": "推理平台工程师",
    "current_work": "KV cache 淘汰策略",
    "bottlenecks": "命中率 60%",
    "stack": "A100×8",
    "near_term_goals": "降本 30%",
    "non_interests": "训练侧",
}


def test_prompt_injects_background_fields():
    msgs = summary_messages({"title": "T", "abstract": "A"}, 1400, BG)
    joined = " ".join(m["content"] for m in msgs)
    for value in BG.values():
        assert value in joined
    assert "1400" in joined


def test_prompt_forbids_invented_numbers():
    msgs = summary_messages({"title": "T", "abstract": "A"}, 1400, BG)
    joined = " ".join(m["content"] for m in msgs)
    assert "不得编造" in joined or "不要编造" in joined


def test_validate_rejects_missing_section():
    assert validate_summary({"one_line": "x", "core_problem": "y"}) != []


def test_validate_rejects_empty_section():
    bad = {k: "内容" * 50 for k in
           ("one_line", "core_problem", "technique", "results", "outlook")}
    bad["results"] = "   "
    assert validate_summary(bad) != []


def test_validate_accepts_complete():
    ok = {k: "内容" * 50 for k in
          ("core_problem", "technique", "results", "outlook")}
    ok["one_line"] = "一句话结论"
    assert validate_summary(ok) == []


def test_validate_rejects_overlong_one_line():
    ok = {k: "内容" * 50 for k in
          ("core_problem", "technique", "results", "outlook")}
    ok["one_line"] = "长" * 81
    assert validate_summary(ok) != []
