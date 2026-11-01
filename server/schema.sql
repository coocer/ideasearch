-- ideasearch 后端表结构（唯一真相）
-- 设计依据：docs/superpowers/specs/2026-11-01-ideasearch-webapp-design.md 第八节

CREATE TABLE IF NOT EXISTS settings (
  id                  INTEGER PRIMARY KEY CHECK (id = 1),
  llm_base_url        TEXT    NOT NULL DEFAULT 'https://api.deepseek.com',
  llm_api_key         TEXT    NOT NULL DEFAULT '',
  llm_model           TEXT    NOT NULL DEFAULT 'deepseek-flash',
  window_days         INTEGER NOT NULL DEFAULT 7,
  background_json     TEXT    NOT NULL DEFAULT '{}',
  title               TEXT    NOT NULL DEFAULT '周观察报告',
  share_minutes       INTEGER NOT NULL DEFAULT 60,
  words_per_minute    INTEGER NOT NULL DEFAULT 150,
  min_papers          INTEGER NOT NULL DEFAULT 5,
  max_papers          INTEGER NOT NULL DEFAULT 10,
  timezone            TEXT    NOT NULL DEFAULT 'Asia/Shanghai',
  arxiv_max_results   INTEGER NOT NULL DEFAULT 150,
  arxiv_delay_seconds REAL    NOT NULL DEFAULT 3.0,
  onboarded_at        TEXT,
  updated_at          TEXT
);

CREATE TABLE IF NOT EXISTS topics (
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  key      TEXT    NOT NULL UNIQUE,
  label    TEXT    NOT NULL,
  keywords TEXT    NOT NULL DEFAULT '[]',
  weight   REAL    NOT NULL DEFAULT 1,
  enabled  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sources (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  kind    TEXT    NOT NULL CHECK (kind IN ('rss', 'arxiv', 'search')),
  name    TEXT    NOT NULL,
  url     TEXT    NOT NULL DEFAULT '',
  config  TEXT    NOT NULL DEFAULT '{}',
  weight  REAL    NOT NULL DEFAULT 1,
  enabled INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS issues (
  id              TEXT PRIMARY KEY,
  title           TEXT NOT NULL DEFAULT '',
  created_at      TEXT NOT NULL,
  window_days     INTEGER NOT NULL,
  window_start    TEXT NOT NULL DEFAULT '',
  window_end      TEXT NOT NULL DEFAULT '',
  config_snapshot TEXT NOT NULL DEFAULT '{}',
  target_words    INTEGER NOT NULL DEFAULT 0,
  status          TEXT NOT NULL DEFAULT 'pending',
  error           TEXT,
  model           TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS papers (
  id              TEXT PRIMARY KEY,
  external_id     TEXT NOT NULL UNIQUE,
  url             TEXT NOT NULL DEFAULT '',
  title           TEXT NOT NULL DEFAULT '',
  authors         TEXT NOT NULL DEFAULT '[]',
  published       TEXT NOT NULL DEFAULT '',
  abstract        TEXT NOT NULL DEFAULT '',
  fulltext        TEXT,
  fulltext_status TEXT NOT NULL DEFAULT 'abstract_only',
  figures         TEXT NOT NULL DEFAULT '[]',
  fetched_at      TEXT
);

CREATE TABLE IF NOT EXISTS issue_papers (
  issue_id       TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
  paper_id       TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  topic_key      TEXT NOT NULL DEFAULT '',
  score          REAL NOT NULL DEFAULT 0,
  selected_rank  INTEGER NOT NULL DEFAULT 0,
  one_line       TEXT NOT NULL DEFAULT '',
  summary_json   TEXT NOT NULL DEFAULT '{}',
  summary_status TEXT NOT NULL DEFAULT 'ok',
  PRIMARY KEY (issue_id, paper_id)
);

CREATE TABLE IF NOT EXISTS news (
  id        TEXT PRIMARY KEY,
  issue_id  TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
  source    TEXT NOT NULL DEFAULT '',
  kind      TEXT NOT NULL DEFAULT 'industry',
  title     TEXT NOT NULL DEFAULT '',
  url       TEXT NOT NULL DEFAULT '',
  published TEXT NOT NULL DEFAULT '',
  one_line  TEXT NOT NULL DEFAULT '',
  detail    TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS deep_reads (
  id              TEXT PRIMARY KEY,
  paper_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  background_hash TEXT NOT NULL,
  model           TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'succeeded',
  content_json    TEXT NOT NULL DEFAULT '{}',
  tokens          INTEGER NOT NULL DEFAULT 0,
  created_at      TEXT NOT NULL,
  UNIQUE (paper_id, background_hash, model)
);

CREATE TABLE IF NOT EXISTS repro_plans (
  id           TEXT PRIMARY KEY,
  paper_id     TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
  model        TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'succeeded',
  evidence_json TEXT NOT NULL DEFAULT '{}',
  estimate_json TEXT NOT NULL DEFAULT '{}',
  plan_md      TEXT NOT NULL DEFAULT '',
  created_at   TEXT NOT NULL,
  UNIQUE (paper_id, model)
);

CREATE TABLE IF NOT EXISTS jobs (
  id          TEXT PRIMARY KEY,
  type        TEXT NOT NULL,
  ref_id      TEXT NOT NULL DEFAULT '',
  status      TEXT NOT NULL DEFAULT 'pending',
  progress    INTEGER NOT NULL DEFAULT 0,
  message     TEXT NOT NULL DEFAULT '',
  error       TEXT,
  created_at  TEXT NOT NULL,
  finished_at TEXT
);
