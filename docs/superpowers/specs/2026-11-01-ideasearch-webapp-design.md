# ideasearch 个人研究雷达 — 设计方案

- 日期：2026-11-01
- 状态：待确认
- 作者：lead（与 coocer 共同梳理）

## 一、意图与为什么

把现有的命令行工具升级成一个**本机单人使用**的研究雷达：按自己配置的研究方向、个人背景、数据源和抓取窗口，自动产出一期"前沿分享"文章；文章里每篇论文先给四段式摘要，再按需展开一篇"理解向"深读；如果你觉得某篇值得投入，再生成一份可交给别的 Agent 执行的复现方案。

为什么现在做：现有 CLI 能抓、能排、能生成，但方向写在 `config.toml` 里、改一次要改文件、产出是一堆静态文件，无法按"我的背景"判断价值，也无法追问。真正缺的不是抓取能力，是**判断**和**交互**。

## 二、目标 / 非目标 / 反目标

### 目标

1. 前端引导式配置：模型 API、研究方向、个人背景、数据源、抓取窗口，配置落盘，**重启不需要再配**。
2. 每次生成一篇文章，含 5~10 篇论文条目，每篇保有四段式摘要（500~1000 字）。
3. 每篇可点"深读"，产出**理解向**解读：没读过这篇的人能跟下来，并据此判断值不值得投入。
4. 每篇可点"复现方案"，产出可交给他人/其他 Agent 执行的方案；并给出**有依据的**成本判断。
5. 全部历史留档，可回看。
6. 代码推到 GitHub，别人 clone 下来配好就能跑。

### 非目标

- 多人、账号、权限、共享工作区
- 云端部署、公网访问
- 系统自动执行论文代码
- 抓取微信公众号、小红书、知乎（无稳定公开接口）
- 定时出刊（时间周期只表示"抓最近 N 天"）

### 反目标（做了就算失败）

- 深读输出"该技术具有重要意义，值得我们关注"这类放在任何论文上都成立的废话
- 把"和你方向相关"当成"对你有价值"
- 报一个看起来很精确的假成本（如"预计 3.2 人天"）而没有依据
- 没有全文却假装读懂了方法细节

## 三、约束

- **本机单用户**，默认只监听 `127.0.0.1`
- **不需要 GPU**：系统不执行论文代码
- Node 只在**构建期**需要（本机已有 v24.15.0）；运行时只有 Python
- 模型 API 通过 OpenAI 兼容接口配置（DeepSeek 为默认），可换任意兼容 provider
- 现有 `ideasearch/` 包（collect / rank / generate / render）保留为领域层，尽量不改
- 测试必须离线可跑，不联网、不烧 token

## 四、方案选择

### 考虑过的三条路

1. **FastAPI + React SPA，单进程单端口**（已选）
2. FastAPI + HTMX/Jinja 服务端渲染，零 Node
3. FastAPI + Next.js 双进程

### 为什么选 1

需求里配置表单、文章卡片、深读展开都是富交互；方案 2 会让实现一路跟框架较劲，且不算真正的"前后端分离"；方案 3 的双端口/CORS/启动顺序对单人本地没有回报。方案 1 拿到分离的好处，运行时仍只有一个东西要启动，满足"重启不用再配"。

### 被否掉的

- 方案 2：不是前后端分离，且放弃已装的前端能力
- 方案 3：复杂度换不到收益

## 五、你已决定的部分

| 项 | 决定 |
|---|---|
| 产物形态 | 一期一篇分享文，含多篇论文条目 |
| 摘要 | 保留原有四段式，500~1000 字 |
| 深读深度 | 理解向：能跟下来 + 能判断值不值得投入 |
| 复现边界 | 只产出方案，不执行代码 |
| 成本依据 | 有依据引用依据；没有则模型估可能性与出 demo 的成本（token 量 / 时间） |
| 背景 | 模板化填写 |
| 部署 | 仅本机，配置持久化 |
| 时间窗口 | 抓最近 7 / 14 天，非定时出刊 |

## 六、我的判断（需要你审）

这几条是我替你定的，理由写在后面，你可以逐条否掉。

1. **配置与数据统一存 SQLite**（不用 JSON 文件）。
   理由：配置、历史、深读结果、复现方案都要持久化，一个库省掉多处一致性问题；且提供导出/导入 JSON 作为备份。API key 明文存本机库中（单人本机，不做加密）。

2. **原文获取优先 arXiv HTML，取不到就明确降级**。
   顺序：`arxiv.org/html/{id}` 摘正文 → 失败则退回 abstract，并在深读结果上打 `fulltext_status=abstract_only`，prompt 里强制要求"说明你只看到摘要，不推断方法细节"。
   **抓取时机**：不在采集阶段抓，而是在**点深读时按需抓**，抓到后缓存进 `papers.fulltext`。理由：一篇文章 10 篇论文，只有被深读的才需要全文，提前抓是浪费请求和时间。
   理由：不引入 PDF 解析依赖；宁可承认信息不足，也不让模型编细节。

3. **不进队列中间件**。用进程内单 worker 线程 + `jobs` 表。
   理由：单人使用，并发是零；Redis/Celery 纯属负担。单 worker 也顺带解决了 SQLite 写并发。

4. **深读与复现方案的结果落库、带缓存**。同一篇重复点击不重复扣 token，除非显式"重新生成"。

5. **保留 CLI**。`python -m ideasearch run` 继续可用，作为无界面/脚本化入口；它复用同一套领域层。

6. **不移动现有包**。`ideasearch/` 原地不动，新增 `server/`（FastAPI）与 `web/`（React）。理由：不动已验证的代码和测试。

## 七、架构

```
web/ (React + Vite + TS + Tailwind + shadcn)
        │  REST /api/v1
        ▼
server/ (FastAPI)  ──  jobs worker (单线程)  ──  ideasearch/ (领域层，原样复用)
        │
        ▼
   ideasearch.db (SQLite)
```

- 构建产物 `web/dist` 由 FastAPI 挂在 `/`，API 在 `/api/v1`，一个进程一个端口。
- 首次启动若库中无配置 → 前端跳转引导页；配置完成后再也不问。

### 目录

```
ideasearch/
├── ideasearch/            # 现有领域层（collect / rank / generate / llm / http / sources）
├── server/
│   ├── app.py             # FastAPI 入口 + 静态托管
│   ├── db.py              # 连接、建表、迁移
│   ├── models.py          # 表定义
│   ├── jobs.py            # 单线程 worker + jobs 表
│   ├── prompts/           # 摘要 / 深读 / 复现方案 的 prompt 模板
│   └── api/               # settings / topics / sources / issues / papers / jobs
├── web/                   # React SPA
├── docs/superpowers/specs/
└── scripts/start.ps1      # 首次构建 + 启动（一条命令）
```

## 八、数据模型

```text
settings (单行)
  llm_base_url, llm_api_key, llm_model, window_days,
  background_json,          -- 个人背景模板的填写结果
  onboarded_at, updated_at

topics
  id, key(unique,不可变), label, keywords(json), weight, enabled

sources
  id, kind(rss|arxiv|conference), name, url, config(json), weight, enabled

issues                     -- 一期文章
  id, title, created_at,
  window_days, window_start, window_end,
  config_snapshot(json),   -- 生成时刻的方向/源/背景快照
  status(pending|running|succeeded|failed), error

papers
  id, issue_id, external_id(arxiv id), url, title, authors(json),
  published, abstract, fulltext(text|null), fulltext_status(full|abstract_only),
  topic_key, score, one_line, summary_json(四段), created_at

deep_reads
  id, paper_id, status, content_json, model, tokens, created_at

repro_plans
  id, paper_id, status, evidence_json, estimate_json, plan_md, created_at

jobs
  id, type(summary|deep_read|repro_plan), ref_id, status,
  progress, message, error, created_at, finished_at
```

**快照的必要性**：方向、权重、背景以后都会改，但历史文章必须能解释"当时是按什么生成的"。`config_snapshot` 保存生成时刻的 topics/background/window。

### 背景模板（我给的草案，你填）

`background_json` 按固定字段存，前端引导页直接渲染成表单。字段是我定的，内容由你填：

| 字段 | 含义 | 为什么要它 |
|---|---|---|
| `role` | 你的角色/岗位 | 决定价值口径：研究员 vs 工程负责人，关心的东西不同 |
| `current_work` | 当前在做的系统或项目（1~3 条） | 深读里"对你有什么用"必须点名这里的内容 |
| `bottlenecks` | 现在卡在哪（性能/成本/效果） | 判断一篇论文"能不能解决你的问题" |
| `stack` | 技术栈与部署环境 | 判断方案是否可落地（比如有没有 GPU 集群） |
| `near_term_goals` | 半年内想达成什么 | 判断"值不值得投入"的时间尺度 |
| `non_interests` | 明确不关心的方向 | 抑制"什么都值得关注"的废话 |

深读 prompt 会把这张表原样注入，并要求 `value_for_you` **指名引用**其中至少一个字段的具体内容。

### 选材规则（沿用现有）

一期论文数 5~10，沿用现有的多样性约束：每个方向先占一席，单方向上限 `ceil(N/方向数)+1`；排序仍按关键词命中 + 时效 + 来源权重。

## 九、API 契约

统一列表信封 `{items,total,page,pageSize}`；统一错误 `{error:{code,message,details}}`。

```text
GET    /api/v1/settings              读取配置（api_key 打码返回）
PUT    /api/v1/settings              保存配置
POST   /api/v1/settings/test         测试模型连通性

GET    /api/v1/topics                列表
POST   /api/v1/topics                新建
PATCH  /api/v1/topics/{key}          更新
DELETE /api/v1/topics/{key}          停用（软删）

GET    /api/v1/sources / POST / PATCH /{id} / DELETE /{id}

POST   /api/v1/issues                生成一期 → 202 + {jobId}
GET    /api/v1/issues                历史列表
GET    /api/v1/issues/{id}           详情（含 papers）
DELETE /api/v1/issues/{id}
GET    /api/v1/issues/{id}/export    导出 Markdown

POST   /api/v1/papers/{id}/deep-read      → 202 + {jobId}
POST   /api/v1/papers/{id}/repro-plan     → 202 + {jobId}
GET    /api/v1/papers/{id}                含已生成的深读/复现

GET    /api/v1/jobs/{id}             进度轮询
```

所有耗时动作一律 202 + jobId，前端轮询（1s 起，退避到 5s 上限）。

## 十、三类生成物的输出契约

### 1. 摘要（沿用现有四段式）

`one_line / core_problem / technique / results / outlook`，合计 500~1000 字。保持不变。

### 2. 深读（新增，理解向）

JSON 字段：

- `why_it_matters`：一句话说清"这篇干了件什么事、为什么这事难"
- `background`：把读懂它需要的前置知识补齐（术语、已有做法、痛点），让没读过的人能跟上
- `what_they_did`：方法，类比优先于公式
- `why_it_works`：为什么这招有效（机理），而不是复述步骤
- `limits`：局限、适用边界、作者没说的代价
- `value_for_you`：**必须点名**你的背景里的具体一句，说明"你在做 X → 这篇能怎么用/为什么用不上"
- `verdict`：只读 / 细读 / 跟进 / 值得投入，四档之一 + 一句理由
- `jargon`：术语表（3~8 条）
- 若 `fulltext_status=abstract_only`，额外字段 `caveat` 说明信息不足

硬约束：`value_for_you` 不许出现"相关""值得关注"这类无指向表述；必须能对应到背景模板里的某个具体字段内容。

### 3. 复现方案（新增）

JSON 字段：

- `evidence`：启发式检查结果——元数据里有没有代码链接、数据集、权重；`evidence_level` ∈ `code_available | partial | none`
- `likelihood`：可复现可能性 低/中/高 + 理由（依据来自 evidence，不是拍脑袋）
- `estimate`：`{token_range:[lo,hi], time_range:[lo,hi]_人天, assumptions:[...]}`，并**明确单位**："token 区间"指用 AI 协作完成该 demo 的大致消耗，用户可按自己配置的模型单价换算
- `missing`：缺哪些信息会导致估不准
- `plan_md`：环境、步骤、最小实现、验收标准、风险
- `handoff_prompt`：一段可直接投喂给 Claude / Codex / 任意模型的提示词

## 十一、成本与节流

- 一期 = 5~10 次摘要调用
- 深读 / 复现 = 各 1 次较大调用，按需触发
- 同一篇不重复生成（结果落库），除非显式重跑
- 生成前展示预估调用次数，避免误触

> 并发口径（澄清）：**job 之间串行**（单 worker 线程依次执行，避免 SQLite 写冲突），
> **单个 job 内部**的模型调用可并发，上限 4，与现有 CLI 的线程池一致；DB 写入统一经一把锁。

## 十二、前端页面

1. **引导/设置**：首次进入；模型 API（含"测试连接"）、背景模板表单、抓取窗口
2. **研究方向**：增删改查、启用开关、权重
3. **数据源**：arXiv 分类、RSS 列表、健康状态
4. **生成**：选窗口 → 预估调用次数 → 生成 → 进度条
5. **文章**：本期卡片列表；展开为四段式；每篇两个按钮（深读 / 复现方案）
6. **历史**：按期存档，可回看、可导出 Markdown

## 十三、风险

| 风险 | 应对 |
|---|---|
| 无全文导致深读变浅 | 明确标注 `abstract_only`，prompt 禁止推断细节；arXiv HTML 失败率作为监控指标 |
| 模型输出正确废话 | `value_for_you` 强制引用背景字段；不合格时重试一次并附校验失败原因 |
| token 跑飞 | 单期上限 + 按需生成 + 结果缓存 |
| SQLite 写并发 | 单 worker 线程串行化 |
| 配置泄露 | 仅本机监听；`.gitignore` 排除 `*.db` 与本地配置；仓库内不放任何 key |

## 十四、留给 builder 的自由

- 前端组件选型细节（shadcn 具体组件、路由库）
- 深读/复现 prompt 的具体措辞与分块策略
- 进度上报粒度
- 索引导出样式
- 是否加 SSE 替代轮询（默认不加）

## 十五、评审澄清（builder check 后）

派了一个未参与讨论的 reviewer 独立读文档，提出 8 个"再往下就得靠猜"的点。逐条处置如下，**标「你的判断」的仍需你定**。

### 1. 背景模板：固定字段 + 字段级校验

采用第八节那张 6 字段表（`role / current_work / bottlenecks / stack / near_term_goals / non_interests`），**结构固定，不做自由散文**。

校验方式：深读 prompt 除正文外必须返回 `cited_background_fields: ["current_work", ...]`，程序校验为非空合法字段名；为空或非法则带"你忽略了读者的背景字段 X"重试一次；仍失败则该篇深读标记 `failed`，**不展示一份编出来的价值判断**。

> **待你定**：默认模板的**口径**。现有 README 和 topics 是"对团队的落地价值"这种团队周报口径，而你说的是个人研究。默认模板该按个人研究员的视角写，还是按团队技术负责人的视角写？这决定陌生人 clone 下来填得顺不顺。

### 2. 文章是否保留 RSS 行业/竞品动态 —— **待你定**

这是产品定位问题，不是实现细节：

- **保留**：需要新增 `kind` 列或独立 news 表、动态用另一套摘要形状（`one_line + detail`）、UI 上动态行不显示深读/复现按钮、导出 Markdown 要多一段
- **去掉**：`rank_news`、`NEWS_TEMPLATE`、竞品类数据源全部移除，产品收窄成 arXiv 纯论文雷达

我的倾向是**保留**——你说"在旧版基础上增加深读"，旧版就有这段；而且只抓 arXiv 会让"竞品动态"这个你原本明确要的东西消失。

### 3. papers 改成全局实体（我的判断）

原设计 `papers.issue_id` 会让同一篇论文在 7 天/14 天窗口重叠时反复出现、反复扣钱。改为：

- `papers` 全局唯一（按 arXiv id）
- `issue_papers` 关联表承载**每次选材才产生**的字段：`score / topic_key / one_line / summary_json`
- 缓存键 = `(paper_id, background_hash, model)`

最后一条很关键：深读里的"对你有什么用"依赖你的背景。背景改了，旧深读必须重算，否则会拿旧背景给你讲价值。

### 4. 失败与降级（我的判断）

- **Web 界面必须有可用 API key 才能生成**；CLI 保留 `--no-llm` 仅供离线开发
- 每篇重试 2 次仍失败 → 该篇 `failed`，**排出文章**并在 UI 标注原因
- 成功篇数 < `min_papers` → 整期 `failed`，不出半成品
- 文章内**不出现**占位或降级文本（现有 `（未启用模型，未做提炼）` 这类输出违背反目标）
- 离线测试断言**失败路径**（排除、整体失败），不再把降级文本当正确结果

### 5. 配置项迁移（我的判断）

`settings` 扩展为：`llm_base_url / llm_api_key / llm_model / window_days / background_json / title / max_papers / min_papers / target_words / timezone / arxiv_max_results / arxiv_delay_seconds`。

- **一条 `sources` = 一个源**；arXiv 源把 `categories` 列表放在 `config` json 里（对应现有一次 OR 查询 + 一次延迟）
- `topics.keywords` 直接映射
- 首次引导**导入现有 config.toml 作为种子**（3 个方向、9 个源、arXiv 分类），不是空库

### 6. 单一配置源（我的判断）

SQLite 是唯一真相。CLI **优先读 DB**；DB 不存在时回退 `config.toml`——这样 clone 下来未引导也能跑、测试也不用建库。引导写库完成后，`config.toml` 退化为"种子"，不再被读取。

### 7. topics.weight 必须真的生效（我的判断）

现状 `score()` 没用到 topic 权重，等于用户设了也看不见效果。改为 `topic_hits * topic.weight`，并补测试。

这是对第六节第 6 条「尽量不改领域层」的**有意例外**——一个看得见却不起作用的配置项比不改更糟。

### 8. conference 类型不做抓取（我的判断）

从 `sources.kind` 移除 `conference`。顶会日历保持内置模块，作为文章固定板块「顶会窗口」，只做会期提醒与 arXiv `comment` 的录用标注，**不新增 OpenReview / ACL Anthology 抓取**——"最近 N 天"本来就不适配会议批量放榜。

## 十六、验收

- [ ] 全新 clone → `scripts/start.ps1` → 浏览器打开 → 完成引导 → 能生成一期文章
- [ ] 关掉再启动，配置仍在，不需要重新填写
- [ ] 每篇论文有四段式摘要，字数在 500~1000
- [ ] 点深读，产出含 `value_for_you` 且点名了背景内容
- [ ] 点复现方案，产出含 `evidence_level`、`likelihood`、`estimate`、`handoff_prompt`
- [ ] 无全文的论文，深读结果带 `caveat`
- [ ] 历史可回看，导出 Markdown 正常
- [ ] 离线测试通过，不联网
