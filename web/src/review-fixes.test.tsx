import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test, vi } from "vitest";

import App from "./App";
import { ClientProvider } from "./api/context";
import type { JobSnapshot, PaperDetail } from "./api/types";
import ReaderPage from "./pages/ReaderPage";
import ReproPanel from "./components/ReproPanel";

const settings = (hasKey: boolean) => ({
  baseUrl: "https://api.deepseek.com",
  model: "deepseek-flash",
  apiKey: hasKey ? "sk-***" : "",
  apiKeyMasked: hasKey,
  windowDays: 7,
  background: {},
  title: "周观察报告",
  shareMinutes: 60,
  wordsPerMinute: 150,
  minPapers: 5,
  maxPapers: 10,
});

const paper = (over: Partial<PaperDetail> = {}): PaperDetail => ({
  id: "p1",
  title: "T",
  url: "https://arxiv.org/abs/1",
  abstract: "A",
  fulltextStatus: "abstract_only",
  deepRead: null,
  reproPlan: null,
  ...over,
});

describe("评审修复回归", () => {
  test("保存 key 后再导航，不被门禁弹回设置页", async () => {
    let hasKey = false;
    const client = {
      settings: {
        get: async () => settings(hasKey),
        update: async () => settings(hasKey),
        test: async () => ({ ok: true }),
      },
      issues: { list: async () => ({ items: [], total: 0, page: 1, pageSize: 0 }) },
    };

    render(
      <ClientProvider client={client as never}>
        <MemoryRouter initialEntries={["/"]}>
          <App />
        </MemoryRouter>
      </ClientProvider>,
    );

    // 被送到设置页
    expect(await screen.findByRole("heading", { name: "设置" })).toBeInTheDocument();

    // 用户保存了 key
    hasKey = true;

    // 再点导航，不应被弹回设置页
    fireEvent.click(screen.getByRole("link", { name: "研究方向" }));
    expect(await screen.findByRole("heading", { name: "研究方向" })).toBeInTheDocument();
  });

  test("有全文时不能标成仅基于摘要", async () => {
    const api = {
      papers: {
        deepRead: vi.fn(),
        detail: async () =>
          paper({
            fulltextStatus: "abstract_only",
            deepRead: {
              why_it_matters: "x",
              background: "y",
              what_they_did: "z",
              why_it_works: "w",
              limits: "v",
              value_for_you: "能替换你现在的淘汰策略",
              verdict: 2,
              jargon: [],
              fulltext_status: "full",
            },
          }),
      },
    };

    render(
      <MemoryRouter>
        <ReaderPage client={api as never} paperId="p1" jobPoll={async () => ({ status: "running", progress: 0, message: "" }) as JobSnapshot} />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/基于全文/)).toBeInTheDocument();
    expect(screen.queryByText(/仅基于摘要/)).not.toBeInTheDocument();
  });

  test("复现方案失败后按钮恢复可用并显示错误", async () => {
    const api = {
      papers: {
        reproPlan: vi.fn(async (_id: string) => ({ jobId: "j1", cached: false })),
        detail: async () => paper({ reproPlan: null }),
      },
    };

    render(
      <ReproPanel
        client={api as never}
        paperId="p1"
        jobPoll={async (): Promise<JobSnapshot> => ({ status: "failed", progress: 0, message: "", error: "模型超时" })}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: /生成复现方案/ }));

    expect(await screen.findByText(/模型超时/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /生成复现方案/ })).toBeEnabled();
  });
});
