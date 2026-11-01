import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, test, vi } from "vitest";

import type { DeepRead, JobSnapshot, PaperDetail } from "../api/types";
import ReaderPage from "./ReaderPage";

const deepRead = (over: Partial<DeepRead> = {}): DeepRead => ({
  why_it_matters: "把并行配置从经验变成可计算",
  background: "前置知识：prefill 与 decode 两段",
  what_they_did: "构造可行集与边界",
  why_it_works: "两段对通信的敏感度相反",
  limits: "缺真实集群验证",
  value_for_you: "能直接替换你现在的淘汰策略",
  verdict: 2,
  jargon: [["TTFT", "首 token 延迟"]],
  fulltext_status: "full",
  ...over,
});

const paper = (over: Partial<PaperDetail> = {}): PaperDetail => ({
  id: "p1",
  title: "Scaling LLM Inference via Parallelism",
  url: "https://arxiv.org/abs/1",
  abstract: "摘要原文",
  fulltextStatus: "full",
  deepRead: null,
  reproPlan: null,
  ...over,
});

const runningJob = async (): Promise<JobSnapshot> => ({
  status: "running",
  progress: 10,
  message: "抓取全文",
});

const renderReader = (ui: React.ReactElement) =>
  render(<MemoryRouter>{ui}</MemoryRouter>);

describe("ReaderPage", () => {
  test("双击深读只提交一次", async () => {
    const deepReadCall = vi.fn(async () => ({ jobId: "j1", cached: false }));
    const api = { papers: { deepRead: deepReadCall, detail: async () => paper() } };

    renderReader(<ReaderPage client={api as never} paperId="p1" jobPoll={runningJob} />);

    const button = await screen.findByRole("button", { name: /开始深读/ });
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => expect(deepReadCall).toHaveBeenCalledTimes(1));
    expect(button).toBeDisabled();
  });

  test("已有深读时直接渲染，不再提交", async () => {
    const deepReadCall = vi.fn();
    const api = {
      papers: { deepRead: deepReadCall, detail: async () => paper({ deepRead: deepRead() }) },
    };

    renderReader(<ReaderPage client={api as never} paperId="p1" jobPoll={runningJob} />);

    expect(await screen.findByText(/把并行配置从经验变成可计算/)).toBeInTheDocument();
    expect(deepReadCall).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: /开始深读/ })).not.toBeInTheDocument();
  });

  test("只拿到摘要时明确标注", async () => {
    const api = {
      papers: {
        deepRead: vi.fn(),
        detail: async () =>
          paper({
            fulltextStatus: "abstract_only",
            deepRead: deepRead({ fulltext_status: "abstract_only" }),
          }),
      },
    };

    renderReader(<ReaderPage client={api as never} paperId="p1" jobPoll={runningJob} />);

    expect(await screen.findByText(/仅基于摘要/)).toBeInTheDocument();
  });

  test("渲染深读各段与判断标尺", async () => {
    const api = {
      papers: { deepRead: vi.fn(), detail: async () => paper({ deepRead: deepRead({ verdict: 3 }) }) },
    };

    renderReader(<ReaderPage client={api as never} paperId="p1" jobPoll={runningJob} />);

    expect(await screen.findByText(/前置知识/)).toBeInTheDocument();
    expect(screen.getByText(/缺真实集群验证/)).toBeInTheDocument();
    expect(screen.getByText(/能直接替换你现在的淘汰策略/)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "阅读深度：深入" })).toBeInTheDocument();
    expect(screen.getByText(/TTFT/)).toBeInTheDocument();
  });

  test("顶部有阅读进度条", async () => {
    const api = {
      papers: { deepRead: vi.fn(), detail: async () => paper({ deepRead: deepRead() }) },
    };

    renderReader(<ReaderPage client={api as never} paperId="p1" jobPoll={runningJob} />);

    expect(await screen.findByRole("progressbar", { name: "阅读进度" })).toBeInTheDocument();
  });
});
