import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import type { JobSnapshot, PaperDetail, ReproPlan } from "../api/types";
import ReproPanel from "./ReproPanel";

const plan: ReproPlan = {
  evidence: {
    level: "none",
    note: "无代码链接",
    likelihood: "中",
    missing: ["带宽未披露"],
    handoff_prompt: "请实现一个最小可运行原型…",
  },
  estimate: { token_range: [1200000, 2500000], time_range_days: [3, 5] },
  planMd: "1. 搭最小拓扑",
};

const paper = (reproPlan: ReproPlan | null): PaperDetail => ({
  id: "p1",
  title: "KV cache migration",
  url: "https://arxiv.org/abs/1",
  abstract: "摘要",
  fulltextStatus: "full",
  deepRead: null,
  reproPlan,
});

const succeeded = async (): Promise<JobSnapshot> => ({ status: "succeeded", progress: 100, message: "" });

describe("ReproPanel", () => {
  test("点击后轮询完成，展示证据等级、成本区间与缺失信息", async () => {
    let detailCalls = 0;
    const api = {
      papers: {
        reproPlan: vi.fn(async (_id: string) => ({ jobId: "j1", cached: false })),
        detail: async () => {
          detailCalls += 1;
          // 第一次没有方案，生成后才有
          return paper(detailCalls === 1 ? null : plan);
        },
      },
    };

    render(<ReproPanel client={api as never} paperId="p1" jobPoll={succeeded} />);

    fireEvent.click(await screen.findByRole("button", { name: /生成复现方案/ }));

    expect(await screen.findByText(/无代码链接/)).toBeInTheDocument();
    expect(screen.getByText(/1,200,000 ~ 2,500,000 token/)).toBeInTheDocument();
    expect(screen.getByText(/3 ~ 5 人天/)).toBeInTheDocument();
    expect(screen.getByText(/带宽未披露/)).toBeInTheDocument();
    expect(screen.getByText(/搭最小拓扑/)).toBeInTheDocument();
  });

  test("已有方案时直接展示，并可重新生成", async () => {
    const api = {
      papers: { reproPlan: vi.fn(), detail: async () => paper(plan) },
    };

    render(<ReproPanel client={api as never} paperId="p1" jobPoll={succeeded} />);

    expect(await screen.findByText(/无代码链接/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /重新生成/ })).toBeInTheDocument();
    expect(api.papers.reproPlan).not.toHaveBeenCalled();
  });
});
