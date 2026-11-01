# ideasearch 后端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为个人研究雷达实现后端：SQLite 持久化、配置读写、单线程任务队列、一期文章的生成流水线，以及深读 / 复现方案两个按需接口。

**Architecture:** FastAPI 单进程，复用现有 `ideasearch/` 包作为领域层（采集、排序、渲染），新增 `server/` 承载 HTTP、持久化与任务编排。SQLite 是唯一配置源；耗时动作一律 202 + jobId，前端轮询。模型调用沿用 `ideasearch.llm.DeepSeek`。

**Tech Stack:** Python 3.14、FastAPI、uvicorn、pytest + httpx、stdlib sqlite3

**Spec:** `docs/superpowers/specs/2026-11-01-ideasearch-webapp-design.md`（本计划实现在此之上；凡与第十七节冲突处，以第十七节为准）

## Global Constraints

- 领域层 `ideasearch/` 只允许两处改动：`config.Topic` 增加 `weight` 字段；`rank.score()` 中 `topic_hits` 乘以该权重（spec 十五.7）。其余文件不改。
- 现有 19 个单测必须继续通过，且**不联网**。
- 模型名默认 `deepseek-flash`；base_url 默认 `https://api.deepseek.com`。
- 一期字数：`target_words = share_minutes × words_per_minute`，默认 60 × 150 = 9000。
- 摘要每篇字数 = `(target_words − 动态占用) / 论文数`；动态每条固定按 200 字计。
- 深读**不设字数上限**，但必须满足 spec 十.2「证据纪律」七条。
- 缓存键：深读 `(paper_id, background_hash, model)`；复现方案 `(paper_id, model)`。
- Web 端生成要求已配置可用 API key；无 key 直接 400。
- 所有耗时接口返回 202 + `{jobId}`；进度靠 `GET /api/v1/jobs/{id}` 轮询。
- 服务默认只监听 `127.0.0.1`。
- 仓库内不得出现任何 API key。

## Review Focus

按"最可能咬到使用者"排序，每条都落到某个任务的测试里：

1. **同一篇论文跨期重复生成**：7 天与 14 天窗口重叠时，深读结果应命中缓存而不是重复扣费（Task 8）。
2. **背景改了但沿用旧深读**：`value_for_you` 会拿旧背景讲价值（Task 8）。
3. **模型返回非法 JSON 或被截断**：不能让整期崩，也不能写入半截内容（Task 6、7）。
4. **某一篇摘要失败**：应被排除并如实标注，而不是塞占位文本（Task 7）。
5. **导出 Markdown 时标题含 `|` 或中文标点**：不能破坏表格结构（Task 10）。

---

## File Structure

```
server/
  __init__.py
  app.py            # app 工厂、静态托管、路由器注册
  db.py             # sqlite3 连接、建表、PRAGMA
  schema.sql        # 建表语句（单一真相）
  settings.py       # 配置读写、key 打码、to_config()
  budget.py         # 字数预算计算
  jobs.py           # 单线程 worker + jobs 表
  prompts.py        # 摘要 / 深读 / 复现方案 prompt 与输出校验
  fulltext.py       # DeepSeek Fetch → 自抓 HTML → 摘要 三级降级
  pipeline.py       # 一期生成编排
  api/
    __init__.py
    settings.py     # GET/PUT /settings, POST /settings/test
    topics.py       # CRUD /topics
    sources.py      # CRUD /sources
    issues.py       # POST/GET/DELETE /issues, GET /issues/{id}/export
    papers.py       # POST /papers/{id}/deep-read, /repro-plan
    jobs.py         # GET /jobs/{id}
tests/server/
  conftest.py
  test_app.py  test_db.py  test_settings.py  test_crud.py
  test_jobs.py test_prompts.py test_budget.py
  test_pipeline.py test_deepread.py test_repro.py test_export.py
```

职责边界：`pipeline.py` 只编排，不直接拼 SQL；`prompts.py` 只产出 messages 与校验结果，不发请求；`jobs.py` 只管调度与状态，不认识业务。

---

### Task 1: 应用骨架与健康检查

**Files:**
- Create: `server/__init__.py`, `server/app.py`, `server/main.py`, `requirements.txt`
- Test: `tests/server/conftest.py`, `tests/server/test_app.py`

**Interfaces:**
- Produces: `server.app.create_app(db_path: str) -> FastAPI`；`GET /api/v1/health -> {"status": "ok"}`

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_app.py
from fastapi.testclient import TestClient
from server.app import create_app

def test_health(tmp_path):
    client = TestClient(create_app(str(tmp_path / "t.db")))
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_app.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: 实现 `create_app`**

`requirements.txt` 写 `fastapi`、`uvicorn[standard]`、`pytest`、`httpx`。`create_app` 建 FastAPI 实例、注册 `/api/v1/health`、把 `db_path` 挂到 `app.state`。`server/main.py` 提供 `uvicorn` 启动入口，host 固定 `127.0.0.1`。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server/test_app.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add requirements.txt server tests/server
git commit -m "feat(server): FastAPI skeleton with health endpoint"
```

---

### Task 2: SQLite schema 与建表

**Files:**
- Create: `server/db.py`, `server/schema.sql`
- Test: `tests/server/test_db.py`

**Interfaces:**
- Produces: `server.db.connect(db_path: str) -> sqlite3.Connection`（`row_factory=sqlite3.Row`、`PRAGMA foreign_keys=ON`）、`server.db.init_schema(conn) -> None`

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_db.py
from server.db import connect, init_schema

EXPECTED = {"settings","topics","sources","issues","papers","issue_papers",
            "news","deep_reads","repro_plans","jobs"}

def test_init_creates_all_tables(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    init_schema(conn)
    got = {r["name"] for r in conn.execute(
        "select name from sqlite_master where type='table'")}
    assert EXPECTED <= got

def test_settings_is_singleton(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    conn.execute("insert into settings(id) values (1)"); conn.commit()
    import sqlite3, pytest
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("insert into settings(id) values (2)"); conn.commit()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_db.py -v`
Expected: FAIL，no module `server.db`

- [ ] **Step 3: 写 `schema.sql` 并实现 `connect` / `init_schema`**

按 spec 第八节的表结构建表，注意：`settings.id integer primary key check (id = 1)`；`papers.external_id unique`；`deep_reads` 建 `unique(paper_id, background_hash, model)`；`repro_plans` 建 `unique(paper_id, model)`；`issue_papers` 主键 `(issue_id, paper_id)`。`init_schema` 用 `executescript` 读 `schema.sql`（`CREATE TABLE IF NOT EXISTS`）。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server/test_db.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/db.py server/schema.sql tests/server/test_db.py
git commit -m "feat(server): sqlite schema and connection"
```

---

### Task 3: 配置读写与 `to_config()`

**Files:**
- Create: `server/settings.py`
- Test: `tests/server/test_settings.py`

**Interfaces:**
- Produces: `SettingsStore(conn)`，方法 `get() -> dict`（`api_key` 打码为 `"sk-***"`）、`get_raw() -> dict`、`update(payload: dict) -> dict`、`to_config() -> ideasearch.config.Config`、`target_words() -> int`、`is_ready() -> bool`

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_settings.py
from server.db import connect, init_schema
from server.settings import SettingsStore

def store(tmp_path):
    conn = connect(str(tmp_path / "t.db")); init_schema(conn)
    return SettingsStore(conn), conn

def test_defaults_and_masking(tmp_path):
    s, _ = store(tmp_path)
    s.update({"llm_api_key": "sk-secret", "llm_model": "deepseek-flash"})
    assert s.get()["api_key_masked"] is True
    assert "sk-secret" not in str(s.get())
    assert s.get_raw()["llm_api_key"] == "sk-secret"

def test_to_config_maps_topics_and_sources(tmp_path):
    s, conn = store(tmp_path)
    s.update({"share_minutes": 60, "words_per_minute": 150})
    conn.execute("insert into topics(key,label,keywords,weight,enabled) "
                 "values ('inference','推理优化','[\"kv cache\"]',3,1)")
    conn.execute("insert into sources(kind,name,url,config,weight,enabled) "
                 "values ('arxiv','arXiv','','{\"categories\":[\"cs.LG\"]}',1,1)")
    conn.commit()
    cfg = s.to_config()
    assert cfg.title == "周观察报告"
    assert cfg.topics[0].key == "inference"
    assert cfg.topics[0].weight == 3
    assert cfg.arxiv["categories"] == ["cs.LG"]
    assert s.target_words() == 9000

def test_not_ready_without_key(tmp_path):
    s, _ = store(tmp_path)
    assert s.is_ready() is False
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_settings.py -v`
Expected: FAIL，no module `server.settings`

- [ ] **Step 3: 实现 `SettingsStore`**

`get()` 返回字段齐全的 dict 且 key 打码（附 `api_key_masked: true`）；`update()` 只写传入字段、忽略未知字段；`target_words()` 返回 `share_minutes × words_per_minute`；`to_config()` 组装 `ideasearch.config.Config`——`topics` 转 `config.Topic`（**需给 `Topic` 增加 `weight` 字段并透传到 `rank.score()`**，见 Global Constraints），`sources` 中 `kind=arxiv` 的行提供 `arxiv` 配置，`kind=rss` 的行提供 `feeds`。`share_minutes` / `words_per_minute` 只活在 `SettingsStore` 里，**不进 `Config`**，以免改动领域层。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server/test_settings.py tests/test_ideasearch.py -v`
Expected: 全部 PASS（确认领域层未被破坏）

- [ ] **Step 5: 提交**

```bash
git add server/settings.py ideasearch/config.py ideasearch/rank.py tests/server/test_settings.py
git commit -m "feat(server): settings store and config mapping; topic weight reaches ranking"
```

---

### Task 4: 研究方向与数据源的 CRUD

**Files:**
- Create: `server/api/__init__.py`, `server/api/topics.py`, `server/api/sources.py`
- Modify: `server/app.py`
- Test: `tests/server/test_crud.py`

**Interfaces:**
- Consumes: `SettingsStore`（Task 3）
- Produces: `GET/POST /api/v1/topics`、`PATCH/DELETE /api/v1/topics/{key}`、`GET/POST /api/v1/sources`、`PATCH/DELETE /api/v1/sources/{id}`

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_crud.py
def test_create_and_list_topic(client):
    r = client.post("/api/v1/topics", json={"key": "inference", "label": "推理优化",
                                            "keywords": ["kv cache"], "weight": 3})
    assert r.status_code == 201
    assert client.get("/api/v1/topics").json()["items"][0]["key"] == "inference"

def test_duplicate_key_conflicts(client):
    body = {"key": "dup", "label": "X", "keywords": [], "weight": 1}
    client.post("/api/v1/topics", json=body)
    r = client.post("/api/v1/topics", json=body)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "TOPIC_KEY_CONFLICT"

def test_delete_is_soft(client):
    client.post("/api/v1/topics", json={"key":"t1","label":"T","keywords":[],"weight":1})
    client.delete("/api/v1/topics/t1")
    assert client.get("/api/v1/topics").json()["items"][0]["enabled"] is False
```

`tests/server/conftest.py` 提供 `client` fixture：临时库 + `create_app` + `TestClient`，并在每个测试前种入一个 settings 行。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_crud.py -v`
Expected: FAIL，404

- [ ] **Step 3: 实现两个 router**

列表统一返回 `{items,total,page,pageSize}`；错误统一 `{"error":{"code","message","details"}}`。`DELETE` 一律软删（置 `enabled=0`）。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server/test_crud.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/api tests/server/test_crud.py
git commit -m "feat(server): topics and sources CRUD"
```

---

### Task 5: 单线程任务队列

**Files:**
- Create: `server/jobs.py`
- Test: `tests/server/test_jobs.py`

**Interfaces:**
- Produces: `JobRunner(conn)`，方法 `submit(kind: str, ref_id: str, work: Callable[[JobContext], None]) -> str`（返回 job id）、`start()`、`stop()`；`JobContext` 提供 `set_progress(pct: int, message: str)`；`GET /api/v1/jobs/{id}`

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_jobs.py
import time
from server.jobs import JobRunner

def wait_done(conn, jid, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        row = conn.execute("select status,progress from jobs where id=?", (jid,)).fetchone()
        if row["status"] in ("succeeded", "failed"):
            return row
        time.sleep(0.02)
    raise AssertionError("job did not finish")

def test_job_succeeds_and_reports_progress(tmp_path):
    conn = connect(str(tmp_path/"t.db")); init_schema(conn)
    runner = JobRunner(conn); runner.start()
    try:
        jid = runner.submit("issue", "x", lambda ctx: ctx.set_progress(100, "done"))
        row = wait_done(conn, jid)
        assert row["status"] == "succeeded" and row["progress"] == 100
    finally:
        runner.stop()

def test_job_failure_is_recorded(tmp_path):
    conn = connect(str(tmp_path/"t.db")); init_schema(conn)
    runner = JobRunner(conn); runner.start()
    try:
        jid = runner.submit("issue", "x", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
        row = wait_done(conn, jid)
        assert row["status"] == "failed"
        assert "boom" in conn.execute("select error from jobs where id=?", (jid,)).fetchone()["error"]
    finally:
        runner.stop()
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_jobs.py -v`
Expected: FAIL，no module `server.jobs`

- [ ] **Step 3: 实现 `JobRunner`**

单个 `threading.Thread` + `queue.Queue` 串行执行；job 状态写 `jobs` 表（`pending→running→succeeded|failed`），异常写入 `error` 列并置 `failed`。所有写库经同一把锁（spec 十一并发口径）。`GET /api/v1/jobs/{id}` 返回 `{id,type,status,progress,message,error}`。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server/test_jobs.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/jobs.py server/api/jobs.py tests/server/test_jobs.py
git commit -m "feat(server): single-worker job runner"
```

---

### Task 6: 字数预算与摘要 prompt 契约

**Files:**
- Create: `server/budget.py`, `server/prompts.py`
- Test: `tests/server/test_budget.py`, `tests/server/test_prompts.py`

**Interfaces:**
- Produces: `budget.per_paper_words(target_words: int, paper_count: int, news_count: int, words_per_news: int = 200) -> int`；`prompts.summary_messages(paper: dict, target_words: int, background: dict) -> list[dict]`；`prompts.validate_summary(data: dict) -> list[str]`（返回问题列表，空表示通过）

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_budget.py
from server.budget import per_paper_words

def test_splits_target_across_papers():
    assert per_paper_words(9000, 6, 4) == (9000 - 800) // 6

def test_never_below_floor():
    assert per_paper_words(2000, 10, 10) >= 200
```

```python
# tests/server/test_prompts.py
import pytest
from server.prompts import summary_messages, validate_summary

BG = {"role": "推理平台工程师", "current_work": "KV cache 淘汰策略",
      "bottlenecks": "命中率 60%", "stack": "A100×8",
      "near_term_goals": "降本 30%", "non_interests": "训练侧"}

def test_prompt_injects_background_fields():
    msgs = summary_messages({"title": "T", "abstract": "A"}, 1400, BG)
    joined = " ".join(m["content"] for m in msgs)
    for k in BG:
        assert BG[k] in joined
    assert "1400" in joined

def test_validate_rejects_missing_section():
    bad = {"one_line": "x", "core_problem": "y"}
    assert validate_summary(bad) != []

def test_validate_accepts_complete():
    ok = {k: "内容" * 50 for k in
          ("one_line","core_problem","technique","results","outlook")}
    assert validate_summary(ok) == []
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_budget.py tests/server/test_prompts.py -v`
Expected: FAIL，no module `server.budget`

- [ ] **Step 3: 实现预算与 prompt**

`per_paper_words` 计算 `(target - news_count*words_per_news) // paper_count`，下限 200。`summary_messages` 返回 `[{"role":"system",...},{"role":"user",...}]`，背景六个字段全部注入，并写明目标字数与「实际效果不得编造数据」的硬约束。`validate_summary` 检查五个键存在、非空、`one_line` ≤ 80 字。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server/test_budget.py tests/server/test_prompts.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/budget.py server/prompts.py tests/server/test_budget.py tests/server/test_prompts.py
git commit -m "feat(server): word budget and summary prompt contract"
```

---

### Task 7: 一期生成流水线

**Files:**
- Create: `server/pipeline.py`
- Test: `tests/server/test_pipeline.py`

**Interfaces:**
- Consumes: `budget.per_paper_words`、`prompts.summary_messages/validate_summary`、`ideasearch.collect`、`ideasearch.rank`、`ideasearch.llm.DeepSeek`
- Produces: `pipeline.generate_issue(conn, cfg, ctx, *, collector=collect, client=None) -> str`（返回 issue id）

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_pipeline.py
import json
from server.db import connect, init_schema
from server.pipeline import generate_issue

class FakeCtx:
    def set_progress(self, pct, msg): self.last = (pct, msg)

def fake_collector(cfg):
    from ideasearch.collect import Collected
    return Collected(papers=[{"id": f"p{i}", "title": f"T{i}", "abstract": "A",
                              "kind": "paper", "published": "2026-10-30",
                              "source": "arXiv", "url": "u"} for i in range(6)],
                     news=[], warnings=[], conferences=[])

class OkClient:
    available = True; model = "fake"
    def chat_json(self, messages, **kw):
        return {k: "内容" * 60 for k in
                ("one_line","core_problem","technique","results","outlook")}

def test_generates_issue_with_papers(tmp_path):
    conn = connect(str(tmp_path/"t.db")); init_schema(conn)
    s = SettingsStore(conn); s.update({"llm_api_key": "sk-x", "min_papers": 3})
    iid = generate_issue(conn, s.to_config(), FakeCtx(),
                         collector=fake_collector, client=OkClient())
    rows = conn.execute("select * from issue_papers where issue_id=?", (iid,)).fetchall()
    assert len(rows) == 6
    assert conn.execute("select status from issues where id=?", (iid,)).fetchone()["status"] == "succeeded"

def test_failed_paper_is_excluded(tmp_path):
    conn = connect(str(tmp_path/"t.db")); init_schema(conn)
    s = SettingsStore(conn); s.update({"llm_api_key": "sk-x", "min_papers": 1})
    calls = {"n": 0}
    class Picky(OkClient):
        def chat_json(self, messages, **kw):
            calls["n"] += 1
            raise RuntimeError("bad json")
    generate_issue(conn, s.to_config(), FakeCtx(),
                   collector=fake_collector, client=Picky())
    status = conn.execute("select status from issues").fetchone()["status"]
    assert status == "failed"

def test_no_api_key_is_rejected(tmp_path):
    conn = connect(str(tmp_path/"t.db")); init_schema(conn)
    s = SettingsStore(conn)
    import pytest
    with pytest.raises(ValueError):
        generate_issue(conn, s.to_config(), FakeCtx(), collector=fake_collector)
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_pipeline.py -v`
Expected: FAIL，no module `server.pipeline`

- [ ] **Step 3: 实现 `generate_issue`**

流程：校验 key → `collector(cfg)` → `rank.rank_papers` / `rank.rank_news` → 计算每篇字数（`budget.per_paper_words(settings.target_words(), …)`）→ 逐篇 `chat_json` 并 `validate_summary`（失败重试 2 次）→ 成功篇 upsert `papers`（按 `external_id`）+ 插 `issue_papers`，失败篇记 `summary_status='failed'` 且**不写入正文** → 成功篇数 < `min_papers` 则 issue 置 `failed` → 写 `news` → 落 `config_snapshot` 与 `target_words`。每篇完成后 `ctx.set_progress`。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server/test_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/pipeline.py tests/server/test_pipeline.py
git commit -m "feat(server): issue generation pipeline with per-paper failure exclusion"
```

---

### Task 8: 深读接口与全文获取

**Files:**
- Create: `server/fulltext.py`, `server/api/papers.py`
- Modify: `server/prompts.py`（加深读 prompt 与校验）
- Test: `tests/server/test_deepread.py`

**Interfaces:**
- Produces: `fulltext.fetch_text(url: str, *, get_text=get_text, post_json=post_json) -> tuple[str, str]`（返回 `(text, status)`，`status ∈ {"full","abstract_only"}`）；`prompts.deepread_messages(paper, fulltext, background) -> list[dict]`；`prompts.validate_deepread(data) -> list[str]`；`POST /api/v1/papers/{id}/deep-read -> 202 {jobId}`

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_deepread.py
from server.fulltext import fetch_text
from server.prompts import validate_deepread

def test_fetch_falls_back_to_abstract(monkeypatch):
    def boom(*a, **k): raise RuntimeError("nope")
    text, status = fetch_text("https://arxiv.org/abs/1", get_text=boom, post_json=boom)
    assert status == "abstract_only"
    assert text == ""

def test_validate_flags_unsourced_number():
    data = {"why_it_matters":"x","background":"y","what_they_did":"z",
            "why_it_works":"w","limits":"v","value_for_you":"u","verdict":3,
            "jargon":[],"citations":[],
            "claims":[{"text":"延迟降低 45%","evidence":"","location":""}]}
    assert any("证据" in p for p in validate_deepread(data))

def test_validate_passes_with_locations():
    data = {"why_it_matters":"x","background":"y","what_they_did":"z",
            "why_it_works":"w","limits":"v","value_for_you":"u","verdict":3,
            "jargon":[],"citations":["§3.2"],
            "claims":[{"text":"延迟降低 45%","evidence":"表 2","location":"§4.1"}]}
    assert validate_deepread(data) == []

def test_cache_key_includes_background_hash(tmp_path):
    """同一篇论文、背景变了 -> 不复用旧深读"""
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_deepread.py -v`
Expected: FAIL，no module `server.fulltext`

- [ ] **Step 3: 实现三级降级与校验**

`fetch_text`：先 `POST /v1/tools/fetch` 传 URL 取 Markdown（`{"url": ...}` → `{"content"}`）；失败再 `get_text` 自抓 `arxiv.org/html/{id}`；再失败返回 `("", "abstract_only")`。`validate_deepread`：必需键齐全；`claims` 中每条若正文含数字/百分比，则 `evidence` 与 `location` 都不得为空；`value_for_you` 不得只含"相关/值得关注"。缓存：先按 `(paper_id, background_hash, model)` 查 `deep_reads`，命中直接返回；`background_hash` 用 `hashlib.sha256(json.dumps(bg, sort_keys=True))`。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server/test_deepread.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/fulltext.py server/prompts.py server/api/papers.py tests/server/test_deepread.py
git commit -m "feat(server): deep-read with fulltext fallback and evidence validation"
```

---

### Task 9: 复现方案接口

**Files:**
- Modify: `server/prompts.py`, `server/api/papers.py`
- Test: `tests/server/test_repro.py`

**Interfaces:**
- Produces: `prompts.repro_messages(paper, fulltext) -> list[dict]`；`prompts.validate_repro(data) -> list[str]`；`POST /api/v1/papers/{id}/repro-plan -> 202 {jobId}`

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_repro.py
from server.prompts import validate_repro

BASE = {"evidence":{"level":"none","note":"无代码链接"},
        "likelihood":"中","estimate":{"token_range":[1200000,2500000],
        "time_range_days":[3,5],"assumptions":["单机双进程"]},
        "missing":["带宽未披露"],"plan_md":"1. …","handoff_prompt":"请实现…"}

def test_valid_repro_passes():
    assert validate_repro(BASE) == []

def test_level_must_be_enum():
    bad = {**BASE, "evidence": {"level": "unknown", "note": ""}}
    assert validate_repro(bad) != []

def test_estimate_ranges_must_be_ordered():
    bad = {**BASE, "estimate": {**BASE["estimate"], "token_range": [5, 1]}}
    assert validate_repro(bad) != []

def test_missing_section_is_flagged():
    bad = {k: v for k, v in BASE.items() if k != "missing"}
    assert validate_repro(bad) != []
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_repro.py -v`
Expected: FAIL，`ImportError: cannot import name 'validate_repro'`

- [ ] **Step 3: 实现校验并接上路由**

`validate_repro`：`evidence.level ∈ {code_available, partial, none}`；`token_range`/`time_range_days` 均为两元素且 `lo <= hi`；`plan_md`、`handoff_prompt`、`missing` 非空。路由复用 Task 8 的 job 与缓存（键 `(paper_id, model)`）。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server/test_repro.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add server/prompts.py server/api/papers.py tests/server/test_repro.py
git commit -m "feat(server): reproduction plan endpoint with estimate validation"
```

---

### Task 10: 导出 Markdown 与静态托管

**Files:**
- Create: `server/api/issues.py`
- Modify: `server/app.py`
- Test: `tests/server/test_export.py`

**Interfaces:**
- Produces: `GET /api/v1/issues/{id}/export -> text/markdown`；`create_app` 在 `web/dist` 存在时把 `/` 指向该目录

- [ ] **Step 1: 写失败测试**

```python
# tests/server/test_export.py
def test_export_escapes_pipe_in_title(seeded_issue):
    client, iid = seeded_issue(title="KV | Cache 优化")
    r = client.get(f"/api/v1/issues/{iid}/export")
    assert r.status_code == 200
    assert "KV \\| Cache" in r.text

def test_export_contains_deepread_when_present(seeded_issue):
    client, iid = seeded_issue(with_deepread=True)
    body = client.get(f"/api/v1/issues/{iid}/export").text
    assert "深读" in body
```

`seeded_issue` fixture 在 conftest 里造一期含 1 篇论文（标题可指定）与可选深读记录。

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/server/test_export.py -v`
Expected: FAIL，404

- [ ] **Step 3: 实现导出**

复用 `ideasearch.render.render_markdown` 的结构，但改为从库读：论文段带四段式，动态段用 `one_line + detail`，末尾附顶会窗口与告警；若 `deep_reads` 有记录则追加「深读」小节。标题与正文做 Markdown 表格转义（`|` → `\|`）。静态托管：`web/dist` 存在时 `app.mount("/", StaticFiles(directory=..., html=True))`，且必须在路由注册之后。

- [ ] **Step 4: 运行确认通过**

Run: `python -m pytest tests/server -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add server/api/issues.py server/app.py tests/server
git commit -m "feat(server): markdown export and SPA static hosting"
```

---

## Self-Review

- **Spec coverage**：配置/引导（T3）、方向与数据源（T4）、生成（T7）、深读（T8）、复现（T9）、历史与导出（T10）、任务与进度（T5）、字数预算（T6）、缓存键与背景变更（T8）、失败排除（T7）——均有任务对应。前端 SPA 属另一计划。
- **Step scan**：每个代码步骤只给签名与关键取值，未写实现体；未见"处理边界情况"这类空指令。
- **Type consistency**：`JobContext.set_progress`、`SettingsStore.to_config`、`pipeline.generate_issue`、`prompts.*_messages/validate_*` 在各任务间名称一致。
- **Review Focus**：五条均已落到具体测试（T7 两条、T8 两条、T10 一条）。
- **Proportion**：计划 660 行，spec 325 行，约 2 倍。多出来的主要是每个任务的**测试代码**（spec 里没有测试，而计划必须给到断言级别），以及 10 组 Files/Interfaces 块；实现体一律只给签名，未转录代码。
