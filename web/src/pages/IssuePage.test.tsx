import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test } from "vitest";

import { ApiError } from "../api/client";
import type { IssueDetail } from "../api/types";
import IssuePage from "./IssuePage";

const detail = (over: Partial<IssueDetail> = {}): IssueDetail => ({
  id: "i1",
  title: "推理系统的三个成本杠杆",
  createdAt: "2026-11-01T10:00:00",
  status: "succeeded",
  targetWords: 9000,
  papers: [
    {
      id: "p1",
      title: "KV | Cache 优化",
      url: "https://arxiv.org/abs/1",
      topicKey: "inference",
      oneLine: "一句话结论",
      summary: {
        core_problem: "问题",
        technique: "手段",
        results: "效果",
        outlook: "启发",
      },
      status: "ok",
    },
  ],
  news: [
    { title: "Meta 把闲置算力转成广告收益", source: "Meta Engineering", oneLine: "要点", detail: "细节", url: "https://x" },
  ],
  ...over,
});

const client = (issue: IssueDetail | (() => Promise<IssueDetail>)) => ({
  issues: { detail: typeof issue === "function" ? issue : async () => issue },
});

describe("IssuePage", () => {
  test("渲染标题、一句话与四段式", async () => {
    render(<MemoryRouter><IssuePage client={client(detail()) as never} issueId="i1" /></MemoryRouter>);

    expect(await screen.findByText(/推理系统的三个成本杠杆/)).toBeInTheDocument();
    expect(screen.getByText(/一句话结论/)).toBeInTheDocument();
    expect(screen.getByText(/核心解决的问题/)).toBeInTheDocument();
    expect(screen.getByText(/后续计划与启发/)).toBeInTheDocument();
  });

  test("行业动态里没有深读入口", async () => {
    render(<MemoryRouter><IssuePage client={client(detail()) as never} issueId="i1" /></MemoryRouter>);

    expect(await screen.findByText(/Meta 把闲置算力转成广告收益/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /深读/ })).not.toBeInTheDocument();
  });

  test("失败的一期显示原因而不是空白", async () => {
    const failing = async () => {
      throw new ApiError(409, "ISSUE_FAILED", "这期生成失败，不展示半成品", {
        reason: "成功摘要 2 篇，少于要求的 5 篇",
      });
    };

    render(<MemoryRouter><IssuePage client={client(failing) as never} issueId="i1" /></MemoryRouter>);

    expect(await screen.findByText(/成功摘要 2 篇，少于要求的 5 篇/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "去生成新一期" })).toHaveAttribute("href", "/generate");
  });

  test("没有指定某一期时给出入口", async () => {
    render(
      <MemoryRouter>
        <IssuePage client={client(detail()) as never} />
      </MemoryRouter>,
    );
    expect(await screen.findByRole("link", { name: "去生成第一期" })).toHaveAttribute("href", "/generate");
  });

  test("摘要默认折叠，点开后可见", async () => {
    render(<MemoryRouter><IssuePage client={client(detail()) as never} issueId="i1" /></MemoryRouter>);

    const summary = await screen.findByText("四段式摘要");
    const details = summary.closest("details");
    expect(details).not.toBeNull();
    expect(details!.open).toBe(false);

    fireEvent.click(summary);
    expect(details!.open).toBe(true);
  });
});

