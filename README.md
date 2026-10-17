# ideasearch · 周观察报告

把「每周翻论文、翻公众号、翻竞品动态」这件事自动化：从 arXiv、顶会、技术博客/公众号镜像源采集信息，
按关注方向（推理优化 / 硬件动态 / 竞品现状）打分筛选，再调用 DeepSeek 逐篇提炼成符合团队规范的周报。

零第三方依赖，只用 Python 3.11+ 标准库。

## 输出长什么样

每期报告按团队规范产出：

1. **表格汇总** —— 一眼扫完本期所有条目；
2. **逐项解读** —— 每项 500~1000 字，固定四段：核心解决的问题 / 核心技术手段 / 实际效果 / 后续计划和启发；
3. **竞品与行业动态** —— 不止论文，包含大厂技术博客、厂商发布等非论文信息；
4. **顶会窗口** —— 当期处于或临近的顶会（ICLR/ICML/NeurIPS/CVPR/ACL/KDD/VLDB/SOSP…）。

同时输出 Markdown、单文件 HTML（自适应深浅色）和结构化 JSON。

## 快速开始

```bash
# 1) 配置密钥
cp .env.example .env        # 填入 DEEPSEEK_API_KEY

# 2) 采集 + 生成（一条龙）
python -m ideasearch run

# 也可以分步：
python -m ideasearch collect                    # 只抓数据，落盘 data/collected-*.json
python -m ideasearch generate --input data/collected-xxx.json

# 没有可用网络或想先看效果：
python -m ideasearch generate --input examples/sample-collected.json --no-llm
```

产物写入 `output/report-<时间戳>.md|.html|.json`。

## 常用参数

| 参数 | 说明 |
|---|---|
| `--limit N` | 本期精读论文数（默认取 `config.toml` 的 `max_papers`，建议 5~10） |
| `--news N` | 行业/竞品动态条数 |
| `--workers N` | 并发调用模型数，默认 4 |
| `--no-llm` | 不调用模型，降级为抽取式摘要（用于离线验证链路） |
| `--config PATH` | 指定其他配置文件 |

## 测试

全部离线，不需要网络和 API Key：

```bash
python -m unittest discover -s tests -v
```

覆盖顶会识别与名称归一化、去重与方向归属、RSS/Atom 解析、Markdown/HTML 渲染转义，
以及「无 key 时降级」和「采集告警透传」两条关键失败路径。

## 配置

`config.toml` 是唯一的配置入口：

- `[topics.*]` —— 关注方向与关键词。关键词既参与 arXiv 检索，也决定条目的方向归属与打分。
- `[arxiv]` —— 分类、回溯天数、单次翻页量、请求间隔（arXiv 有频率要求，默认 3 秒）。
- `[[feeds]]` —— 行业动态 RSS/Atom 源，`kind` 区分 `competitor` / `industry` / `vendor`，`weight` 影响排序。

### 关于数据来源的现状

- **arXiv**：走官方 Atom API，稳定可用。
- **微信公众号**：没有公开 API。默认走可转载的技术媒体 RSS 间接覆盖（量子位、新智元、InfoQ 中文、36氪）。
  机器之心 `/rss` 目前返回的是反爬 HTML 页面而不是 feed，无法接入；程序会把这类情况明确报成
  「源返回 HTML 页面而非 RSS/Atom」，而不是含糊的解析失败。
- **顶会**：程序内置会期日历用于提醒与录用标注，不抓取会议官网全文。
- **小红书 / 知乎**：无稳定公开接口，建议人工补充。

## 工作原理

```
sources/          collect.py            rank.py               generate.py          render.py
arXiv ─────┐                         去重 + 方向归属        逐项调用 DeepSeek     Markdown / HTML
RSS/Atom ──┼──► Collected ─────────► 打分排序 TopN  ─────► 四段式 JSON   ─────► 表格 + 逐项解读
顶会日历 ──┘    (含 warnings)        保证方向多样性          (并发, 失败降级)
```

- 单个源失败不影响整体：失败会以「采集告警」形式出现在报告末尾，而不是让任务崩掉。
- **多面性有硬约束**：每个方向先占一席，单方向最多不超过 `上限`（6 篇/3 方向 => 每方向 ≤3）；
  动态先保证 competitor / vendor / industry 各一条，并对单一来源限流，避免某一家的稿子刷屏。
- 模型调用失败或未配置 key 时，自动降级为抽取式摘要，并在报告中标注。
- `实际效果` 一段明确要求「材料没有量化数据就写没有」，避免模型编造指标。

## 目录结构

```
ideasearch/
├── config.toml              # 关注方向、arXiv 参数、RSS 源
├── ideasearch/
│   ├── cli.py               # collect / generate / run
│   ├── collect.py           # 采集编排（单源失败降级）
│   ├── rank.py              # 去重、方向归属、打分
│   ├── generate.py          # 提示词与四段式提炼
│   ├── render.py            # Markdown / HTML 渲染
│   ├── llm.py               # DeepSeek 客户端
│   ├── http.py              # stdlib HTTP（重试 + TLS 降级）
│   └── sources/             # arxiv / rss / conferences
├── examples/sample-collected.json
└── output/                  # 生成结果（已 gitignore）
```

## 环境变量

| 变量 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | 必填，DeepSeek API Key |
| `DEEPSEEK_MODEL` | 可选，默认 `deepseek-chat` |
| `IDEASEARCH_STRICT_TLS` | 设为 `1` 时禁止 TLS 降级（默认允许一次性降级并告警） |

> TLS 降级说明：部分环境根证书库缺失 arXiv 证书链的签发者。程序会先严格校验，
> 仅在校验失败时降级重试一次，并把原因写进报告告警。可通过 `IDEASEARCH_STRICT_TLS=1` 关闭。

## 授权

MIT
