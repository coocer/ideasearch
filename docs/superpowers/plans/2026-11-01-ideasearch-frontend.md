# ideasearch 前端 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现个人研究雷达的 Web 前端：配置引导、方向与数据源管理、一期生成与进度、文章阅读、深读阅读模式、复现方案与导出。

**Architecture:** Vite + React + TypeScript 单页应用，手写 CSS 设计令牌（不引 Tailwind/shadcn），构建产物 `web/dist` 由已实现的 FastAPI 静态托管，运行时只有一个进程一个端口。所有耗时动作走「POST 拿 jobId → 轮询 /jobs/{id} → 回读资源」。

**Tech Stack:** React 18、TypeScript、Vite、react-router-dom、Vitest + @testing-library/react + jsdom

**Spec:** `docs/superpowers/specs/2026-11-01-ideasearch-webapp-design.md`（第十七节为最新口径）
**Backend contract:** `server/api/*.py`（已实现并通过 80 个测试）

## Global Constraints

- 只调用已实现的 `/api/v1` 接口，不新增后端行为。缺失能力记 Ruling，不擅自改后端。
- 设计令牌固定（见下），不得替换为 Tailwind 默认色板：
  `--paper:#EFF1EE --surface:#FAFBFA --ink:#14181A --ink2:#59635F --ink3:#8A948F --rule:#D3D9D4 --rule-soft:#E3E7E3 --signal:#B23A0E --signal-soft:#F3E7E1 --cool:#2F5E5B --cool-soft:#E4EDEB --warn:#8A6A1F`
- 字体：标题 `"Songti SC","SimSun",Georgia,serif`；正文 `"Microsoft YaHei","PingFang SC",system-ui,sans-serif`。
- 阅读深度只有三档：`1 了解 / 2 关注 / 3 深入`。
- 错误信封统一 `{"error":{"code","message","details"}}`；前端不得只显示 `detail`。
- 构建产物只落 `web/dist`；不新增开发期以外的服务端进程。
- 无障碍底线：键盘焦点可见、`prefers-reduced-motion` 下关闭动效、错误有文本说明。
- 测试不发真实网络：`fetch` 由测试注入。
- **依赖注入约定**：每个页面接受 `client` 属性（生产环境由 `main.tsx` 提供单例，测试传假实现），接受可选 `params`（生产环境缺省时用 `useParams()`），涉及长任务的页面接受可选 `jobPoll`（缺省用 `useJob`）。测试不得 mock 模块，只注入。

## Review Focus

按"最可能咬到使用者"排序，每条都要落到某个任务的测试：

1. **失败的一期**：后端对 `status=failed` 返回 409 `ISSUE_FAILED`，前端不能白屏或显示空文章（Task 7）。
2. **job 轮询失败或超时**：不能无限转圈（Task 2、6）。
3. **首次进入空库**：没有 settings、没有历史时，必须落到引导页而不是空列表（Task 3、10）。
4. **重复点击深读**：按钮必须立即禁用，避免重复提交与重复计费（Task 8）。
5. **超长标题 / 窄屏**：论文标题与术语不得溢出或压掉操作按钮（Task 7、9）。

---

## File Structure

```
web/
  index.html
  package.json  tsconfig.json  vite.config.ts  vitest.setup.ts
  src/
    main.tsx                  # 挂载 + Router
    App.tsx                   # 左栏 + 路由表
    styles/tokens.css         # 设计令牌（唯一来源）
    styles/app.css            # 布局与组件样式
    api/types.ts              # 与后端一一对应的类型
    api/client.ts             # fetch 封装、ApiError、job 轮询
    hooks/useJob.ts           # 轮询 hook（退避、失败即停）
    components/Rail.tsx       # 左栏导航
    components/Gauge.tsx      # 三档标尺
    components/Field.tsx      # 表单字段
    components/Loading.tsx    # 骨架/转圈
    pages/SetupPage.tsx       # 引导 / 设置
    pages/TopicsPage.tsx      # 研究方向
    pages/SourcesPage.tsx     # 数据源（Web Search / arXiv / RSS）
    pages/GeneratePage.tsx    # 生成 + 进度
    pages/IssuePage.tsx       # 文章
    pages/ReaderPage.tsx      # 全屏阅读模式
    pages/HistoryPage.tsx     # 历史
```

职责边界：`api/client.ts` 只做传输与错误归一化；`pages/*` 只组装 UI；组件不直接 fetch。

---

### Task 1: 工程骨架与设计令牌

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`, `web/vitest.setup.ts`
- Create: `web/src/main.tsx`, `web/src/App.tsx`, `web/src/styles/tokens.css`, `web/src/styles/app.css`, `web/src/components/Rail.tsx`
- Test: `web/src/App.test.tsx`

**Interfaces:**
- Produces: `<App />` 渲染左栏，含六个导航项文本；`vite build` 输出到 `web/dist`

- [ ] **Step 1: 写失败测试**

```tsx
// web/src/App.test.tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "./App";

test("左栏列出六个入口", () => {
  render(<MemoryRouter><App /></MemoryRouter>);
  for (const label of ["本期文章", "生成新一期", "研究方向", "数据源", "历史文章", "设置"]) {
    expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
  }
});
```

- [ ] **Step 2: 安装依赖并确认测试失败**

Run: `cd web && npm install && npx vitest run src/App.test.tsx`
Expected: FAIL，找不到 `./App`

- [ ] **Step 3: 建骨架**

`package.json` 依赖 `react`、`react-dom`、`react-router-dom`；开发依赖 `vite`、`@vitejs/plugin-react`、`typescript`、`vitest`、`jsdom`、`@testing-library/react`、`@testing-library/jest-dom`。`vite.config.ts` 里 `build.outDir = "dist"`，`test.environment = "jsdom"`、`test.setupFiles = ["./vitest.setup.ts"]`。`tokens.css` 落 Global Constraints 里的变量与字体栈。`App.tsx` 用 `<Routes>` 占位六个页面，左栏用 `<Link>`。

- [ ] **Step 4: 确认测试通过并构建**

Run: `cd web && npx vitest run src/App.test.tsx && npm run build`
Expected: 1 passed；`dist/index.html` 存在

- [ ] **Step 5: 提交**

```bash
git add web
git commit -m "feat(web): vite+react skeleton with design tokens"
```

---

### Task 2: API 客户端与 job 轮询

**Files:**
- Create: `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/hooks/useJob.ts`
- Test: `web/src/api/client.test.ts`, `web/src/hooks/useJob.test.tsx`

**Interfaces:**
- Produces: `createClient(fetchImpl?) -> { settings, topics, sources, issues, papers, jobs }`；`ApiError { status, code, message, details }`；`useJob(jobId, { intervalMs, timeoutMs }) -> { status, progress, message, error }`

- [ ] **Step 1: 写失败测试**

```ts
// web/src/api/client.test.ts
import { createClient, ApiError } from "./client";

test("把 error 信封转成 ApiError", async () => {
  const fake = async () => new Response(
    JSON.stringify({ error: { code: "ISSUE_FAILED", message: "这期生成失败", details: { reason: "x" } } }),
    { status: 409, headers: { "content-type": "application/json" } });
  const api = createClient(fake as typeof fetch);
  await expect(api.issues.detail("i1")).rejects.toMatchObject({
    status: 409, code: "ISSUE_FAILED", message: "这期生成失败",
  });
});

test("成功时返回解析后的 JSON", async () => {
  const fake = async () => new Response(JSON.stringify({ items: [] }),
    { status: 200, headers: { "content-type": "application/json" } });
  const api = createClient(fake as typeof fetch);
  expect(await api.topics.list()).toEqual({ items: [] });
});
```

```tsx
// web/src/hooks/useJob.test.tsx
import { renderHook, waitFor } from "@testing-library/react";
import { useJob } from "./useJob";

test("轮询到 succeeded 就停", async () => {
  let calls = 0;
  const fetchJob = async () => ({ status: ++calls < 2 ? "running" : "succeeded", progress: 50, message: "" });
  const { result } = renderHook(() => useJob("j1", { fetchJob, intervalMs: 5 }));
  await waitFor(() => expect(result.current.status).toBe("succeeded"));
  expect(calls).toBe(2);
});
```

- [ ] **Step 2: 确认失败**

Run: `cd web && npx vitest run src/api/client.test.ts src/hooks/useJob.test.tsx`
Expected: FAIL，模块不存在

- [ ] **Step 3: 实现**

`client.ts`：`request(path, init)` 统一解析 JSON，非 2xx 时读 `body.error` 抛 `ApiError`；`fetch` 可注入。`types.ts` 按后端字段命名（`oneLine`、`summary`、`progress`、`windowDays` 等）。`useJob`：从 `pending/running` 轮询到 `succeeded|failed`，指数退避至上限，超过 `timeoutMs` 置 `status="timeout"` 并停止；组件卸载时清定时器。

- [ ] **Step 4: 确认通过**

Run: `cd web && npx vitest run src/api/client.test.ts src/hooks/useJob.test.tsx`
Expected: 两个文件全过

- [ ] **Step 5: 提交**

```bash
git add web/src/api web/src/hooks
git commit -m "feat(web): api client with error envelope and job polling"
```

---

### Task 3: 设置 / 引导页

**Files:**
- Create: `web/src/pages/SetupPage.tsx`, `web/src/components/Field.tsx`
- Test: `web/src/pages/SetupPage.test.tsx`

**Interfaces:**
- Consumes: `client.settings.get()/update()/test()`
- Produces: 页面在 `apiKeyMasked` 为真时回填占位符 `sk-***`，提交时不覆盖真实 key

- [ ] **Step 1: 写失败测试**

```tsx
test("回填打码后的 key，且保存时不下发占位符", async () => {
  const update = vi.fn(async (p) => p);
  const api = { settings: { get: async () => ({ llmModel: "deepseek-flash", llmApiKey: "sk-***", apiKeyMasked: true, backgroundJson: { role: "工程师" }, windowDays: 7, shareMinutes: 60, wordsPerMinute: 150 }), update, test: async () => ({ ok: true }) } };
  render(<SetupPage client={api as any} />);
  const key = await screen.findByLabelText("API Key");
  expect(key).toHaveValue("sk-***");
  fireEvent.click(screen.getByRole("button", { name: "保存" }));
  await waitFor(() => expect(update).toHaveBeenCalled());
  expect(JSON.stringify(update.mock.calls[0][0])).not.toContain("sk-***");
});

test("没有 key 时提示去填写", async () => {
  const api = { settings: { get: async () => ({ llmApiKey: "", apiKeyMasked: true, backgroundJson: {}, windowDays: 7, shareMinutes: 60, wordsPerMinute: 150 }), update: async (p) => p, test: async () => ({ ok: false }) } };
  render(<SetupPage client={api as any} />);
  expect(await screen.findByText(/还需要填写 API Key/)).toBeInTheDocument();
});
```

- [ ] **Step 2: 确认失败**：Run: `cd web && npx vitest run src/pages/SetupPage.test.tsx` → FAIL

- [ ] **Step 3: 实现**

六项：接口地址、模型名、API Key、抓取窗口（7/14）、分享时长、背景模板六字段。背景模板字段标签固定为「角色 / 当前在做的系统 / 现在的瓶颈 / 技术栈与环境 / 半年内目标 / 明确不关心的方向」。`backgroundJson` 以对象提交。含「测试连接」按钮显示 `{ok}` 结果。

- [ ] **Step 4: 确认通过**：Run 同上 → PASS

- [ ] **Step 5: 提交**

```bash
git add web/src/pages/SetupPage.tsx web/src/components/Field.tsx web/src/pages/SetupPage.test.tsx
git commit -m "feat(web): setup page with masked key round-trip"
```

---

### Task 4: 研究方向页

**Files:**
- Create: `web/src/pages/TopicsPage.tsx`
- Test: `web/src/pages/TopicsPage.test.tsx`

**Interfaces:**
- Consumes: `client.topics.list()/create()/patch()/remove()`
- Produces: 权重三档按钮（1/2/3）、启用开关、删除为软删

- [ ] **Step 1: 写失败测试**

```tsx
test("切换权重调用 patch", async () => {
  const patch = vi.fn(async () => ({}));
  const api = { topics: { list: async () => ({ items: [{ key: "inference", label: "推理优化", keywords: ["kv cache"], weight: 1, enabled: true }] }), create: vi.fn(), patch, remove: vi.fn() } };
  render(<TopicsPage client={api as any} />);
  fireEvent.click(await screen.findByRole("button", { name: "权重 3" }));
  await waitFor(() => expect(patch).toHaveBeenCalledWith("inference", { weight: 3 }));
});
```

- [ ] **Step 2: 确认失败** → FAIL

- [ ] **Step 3: 实现**：列表 + 新建表单（key/label/keywords 逗号分隔/weight）+ 停用按钮。冲突 409 时在行内显示后端 `message`。

- [ ] **Step 4: 确认通过**

- [ ] **Step 5: 提交**

```bash
git add web/src/pages/TopicsPage.tsx web/src/pages/TopicsPage.test.tsx
git commit -m "feat(web): topics page"
```

---

### Task 5: 数据源页

**Files:**
- Create: `web/src/pages/SourcesPage.tsx`
- Test: `web/src/pages/SourcesPage.test.tsx`

**Interfaces:**
- Consumes: `client.sources.list()/create()/patch()/remove()`
- Produces: 三段式布局（Web Search / arXiv / RSS），只开 Web Search 也能用

- [ ] **Step 1: 写失败测试**

```tsx
test("三类来源分组渲染", async () => {
  const api = { sources: { list: async () => ({ items: [
    { id: 1, kind: "search", name: "DeepSeek Search", url: "", config: {}, weight: 1, enabled: true },
    { id: 2, kind: "arxiv", name: "arXiv", url: "", config: { categories: ["cs.LG"] }, weight: 1, enabled: true },
    { id: 3, kind: "rss", name: "量子位", url: "https://x", config: {}, weight: 1, enabled: true },
  ] }), create: vi.fn(), patch: vi.fn(), remove: vi.fn() } };
  render(<SourcesPage client={api as any} />);
  expect(await screen.findByRole("heading", { name: "Web Search" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "arXiv" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "RSS 源" })).toBeInTheDocument();
});
```

- [ ] **Step 2: 确认失败** → FAIL

- [ ] **Step 3: 实现**：按 `kind` 分三段；arXiv 行展示 `config.categories` 标签；RSS 行可加/停用；每段顶部一句用途说明（Web Search 那段写明「不用配源，按方向关键词自动搜」）。

- [ ] **Step 4: 确认通过**

- [ ] **Step 5: 提交**

```bash
git add web/src/pages/SourcesPage.tsx web/src/pages/SourcesPage.test.tsx
git commit -m "feat(web): sources page"
```

---

### Task 6: 生成页与进度

**Files:**
- Create: `web/src/pages/GeneratePage.tsx`, `web/src/components/Loading.tsx`
- Test: `web/src/pages/GeneratePage.test.tsx`

**Interfaces:**
- Consumes: `client.issues.create()`（202 + jobId）、`useJob`
- Produces: 生成中禁用按钮；成功后跳 `/issues/:id`

- [ ] **Step 1: 写失败测试**

```tsx
test("点击生成后禁用按钮并显示进度", async () => {
  const create = vi.fn(async () => ({ jobId: "j1" }));
  const api = { settings: { get: async () => ({ shareMinutes: 60, wordsPerMinute: 150, windowDays: 7 }) },
                issues: { create } };
  render(<GeneratePage client={api as any} jobPoll={async () => ({ status: "running", progress: 40, message: "生成 3/6 篇摘要" })} />);
  fireEvent.click(await screen.findByRole("button", { name: "开始生成" }));
  await waitFor(() => expect(create).toHaveBeenCalled());
  expect(screen.getByRole("button", { name: /生成中/ })).toBeDisabled();
  expect(await screen.findByText(/生成 3\/6 篇摘要/)).toBeInTheDocument();
});
```

- [ ] **Step 2: 确认失败** → FAIL

- [ ] **Step 3: 实现**：显示预估（`篇数 × 摘要 + 动态` 的调用次数与按分享时长折算的字数），生成中展示进度条与阶段文案；400 `NO_API_KEY` 时引导去设置页。

- [ ] **Step 4: 确认通过**

- [ ] **Step 5: 提交**

```bash
git add web/src/pages/GeneratePage.tsx web/src/components/Loading.tsx web/src/pages/GeneratePage.test.tsx
git commit -m "feat(web): generate page with job progress"
```

---

### Task 7: 文章页

**Files:**
- Create: `web/src/pages/IssuePage.tsx`, `web/src/components/Gauge.tsx`
- Test: `web/src/pages/IssuePage.test.tsx`

**Interfaces:**
- Consumes: `client.issues.detail(id)`
- Produces: `<Gauge level={1|2|3} />` 渲染「了解/关注/深入」；失败的一期显示 409 原因

- [ ] **Step 1: 写失败测试**

```tsx
test("渲染论文标题、一句话与三档标尺", async () => {
  const api = { issues: { detail: async () => ({
    id: "i1", title: "一期", status: "succeeded", targetWords: 9000,
    papers: [{ id: "p1", title: "KV | Cache 优化", topicKey: "inference",
               oneLine: "一句话结论", summary: { core_problem: "问题", technique: "手段", results: "效果", outlook: "启发" },
               status: "ok" }],
    news: [] }) } };
  render(<IssuePage client={api as any} params={{ id: "i1" }} />);
  expect(await screen.findByText(/KV \| Cache 优化/)).toBeInTheDocument();
  expect(screen.getByRole("img", { name: "阅读深度：关注" })).toBeInTheDocument();
});

test("失败的一期显示原因而不是空白", async () => {
  const api = { issues: { detail: async () => { throw new ApiError(409, "ISSUE_FAILED", "这期生成失败", { reason: "成功摘要 2 篇，少于要求的 5 篇" }); } } };
  render(<IssuePage client={api as any} params={{ id: "i1" }} />);
  expect(await screen.findByText(/成功摘要 2 篇/)).toBeInTheDocument();
});
```

- [ ] **Step 2: 确认失败** → FAIL

- [ ] **Step 3: 实现**：标题 + 元信息（字数、篇数、模型）+ 论文列表（标题、方向、一句话、可折叠四段式）+ 动态段（无深读按钮）+ 顶会窗口占位（后端暂未返回，留空不报错）。折叠用 `<details>`，键盘可达。

- [ ] **Step 4: 确认通过**

- [ ] **Step 5: 提交**

```bash
git add web/src/pages/IssuePage.tsx web/src/components/Gauge.tsx web/src/pages/IssuePage.test.tsx
git commit -m "feat(web): issue page with depth gauge and failed-issue state"
```

---

### Task 8: 深读与全屏阅读模式

**Files:**
- Create: `web/src/pages/ReaderPage.tsx`
- Modify: `web/src/pages/IssuePage.tsx`（加「进入阅读模式」按钮）
- Test: `web/src/pages/ReaderPage.test.tsx`

**Interfaces:**
- Consumes: `client.papers.deepRead(id)`（202）、`client.papers.detail(id)`、`useJob`
- Produces: 路由 `/read/:paperId`；点击后按钮立即禁用

- [ ] **Step 1: 写失败测试**

```tsx
test("点击深读后按钮立即禁用，不重复提交", async () => {
  const deepRead = vi.fn(async () => ({ jobId: "j1", cached: false }));
  const api = { papers: { deepRead, detail: async () => ({ id: "p1", title: "T", deepRead: null }) } };
  render(<ReaderPage client={api as any} params={{ paperId: "p1" }} jobPoll={async () => ({ status: "running", progress: 10, message: "抓取全文" })} />);
  const btn = await screen.findByRole("button", { name: /开始深读/ });
  fireEvent.click(btn);
  fireEvent.click(btn);
  await waitFor(() => expect(deepRead).toHaveBeenCalledTimes(1));
});
```

- [ ] **Step 2: 确认失败** → FAIL

- [ ] **Step 3: 实现**：全屏阅读布局（正文 37em、宋体、行高 1.95、顶部进度条）；渲染 `why_it_matters / background / what_they_did / why_it_works / limits / value_for_you / jargon / verdict`；`value_for_you` 里若含背景关键词用 `mark` 高亮；`fulltextStatus==="abstract_only"` 时显示「仅基于摘要」提示。

- [ ] **Step 4: 确认通过**

- [ ] **Step 5: 提交**

```bash
git add web/src/pages/ReaderPage.tsx web/src/pages/ReaderPage.test.tsx web/src/pages/IssuePage.tsx
git commit -m "feat(web): full-page reader with deduped deep-read trigger"
```

---

### Task 9: 复现方案与导出

**Files:**
- Create: `web/src/components/ReproPanel.tsx`
- Modify: `web/src/pages/IssuePage.tsx`
- Test: `web/src/components/ReproPanel.test.tsx`

**Interfaces:**
- Consumes: `client.papers.reproPlan(id)`（202）、`client.papers.detail(id)` 里的 `reproPlan`、`client.issues.export(id)`
- Produces: 展示 `evidence.level / likelihood / estimate / missing / planMd`，并提供「复制提示词」

- [ ] **Step 1: 写失败测试**

```tsx
test("展示证据等级与成本区间，缺信息单独列出", async () => {
  const api = { papers: { reproPlan: async () => ({ jobId: "j1" }), detail: async () => ({ id: "p1", reproPlan: {
    evidence: { level: "none", note: "无代码链接", likelihood: "中", missing: ["带宽未披露"], handoff_prompt: "请实现…" },
    estimate: { token_range: [1200000, 2500000], time_range_days: [3, 5] },
    planMd: "1. 搭最小拓扑" } }) } };
  render(<ReproPanel client={api as any} paperId="p1" jobPoll={async () => ({ status: "succeeded" })} />);
  fireEvent.click(screen.getByRole("button", { name: /生成复现方案/ }));
  expect(await screen.findByText(/无代码链接/)).toBeInTheDocument();
  expect(screen.getByText(/1,200,000/)).toBeInTheDocument();
  expect(screen.getByText(/带宽未披露/)).toBeInTheDocument();
});
```

- [ ] **Step 2: 确认失败** → FAIL

- [ ] **Step 3: 实现**：成本区间用千分位；`missing` 用列表而非长段落；「导出 Markdown」以 `text/markdown` 下载，文件名带期号。

- [ ] **Step 4: 确认通过**

- [ ] **Step 5: 提交**

```bash
git add web/src/components/ReproPanel.tsx web/src/components/ReproPanel.test.tsx web/src/pages/IssuePage.tsx
git commit -m "feat(web): repro plan panel and markdown export"
```

---

### Task 10: 历史页与收尾

**Files:**
- Create: `web/src/pages/HistoryPage.tsx`
- Modify: `web/src/App.tsx`（空库重定向到 `/setup`）
- Test: `web/src/pages/HistoryPage.test.tsx`

**Interfaces:**
- Consumes: `client.issues.list()`
- Produces: 空列表时给"去生成第一期"的入口；应用启动时若 `settings` 无 key 则重定向

- [ ] **Step 1: 写失败测试**

```tsx
test("空历史给出下一步动作", async () => {
  const api = { issues: { list: async () => ({ items: [] }) } };
  render(<HistoryPage client={api as any} />);
  expect(await screen.findByRole("link", { name: /去生成第一期/ })).toBeInTheDocument();
});
```

- [ ] **Step 2: 确认失败** → FAIL

- [ ] **Step 3: 实现**：历史列表（标题、日期、篇数、状态徽章）；`/` 路由在无 key 时 `<Navigate to="/setup" replace />`；补 `prefers-reduced-motion` 与焦点样式。

- [ ] **Step 4: 确认通过并整体构建**

Run: `cd web && npx vitest run && npm run build`
Expected: 全绿；`dist/` 产出

- [ ] **Step 5: 提交**

```bash
git add web
git commit -m "feat(web): history page, onboarding redirect and a11y polish"
```

---

## Self-Review

- **Spec coverage**：设置/引导（T3）、方向（T4）、数据源含 Web Search（T5）、生成与进度（T6）、文章与三档标尺（T7）、阅读模式（T8）、复现与导出（T9）、历史（T10）。spec 十二节的六个页面均有对应任务。
- **Step scan**：代码步骤只给签名、字段名与关键取值；未写实现体。
- **Type consistency**：`client.papers.deepRead/detail/reproPlan`、`client.issues.create/detail/list/export`、`useJob` 的 `{status,progress,message,error}` 在各任务间一致。
- **Review Focus**：五条分别落在 T7（失败期）、T2/T6（轮询）、T3/T10（空库）、T8（重复点击）、T7/T9（长标题与窄屏）。
- **Proportion**：本计划比后端计划短，前端逻辑更薄；未把组件实现写进计划。
