import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import type { IssueListItem, JobSnapshot } from "../api/types";
import GeneratePage from "./GeneratePage";

const settings = {
  baseUrl: "https://api.deepseek.com",
  model: "deepseek-flash",
  apiKey: "sk-***",
  apiKeyMasked: true,
  windowDays: 7,
  background: {},
  title: "周观察报告",
  shareMinutes: 60,
  wordsPerMinute: 150,
  minPapers: 5,
  maxPapers: 10,
};

const issue = (id: string): IssueListItem => ({
  id,
  title: "一期",
  createdAt: "2026-11-01T10:00:00",
  windowDays: 7,
  status: "succeeded",
  targetWords: 9000,
});

describe("GeneratePage", () => {
  test("点击生成后禁用按钮并显示进度", async () => {
    const create = vi.fn(async () => ({ jobId: "j1" }));
    const api = {
      settings: { get: async () => settings },
      issues: { create, list: async () => ({ items: [], total: 0, page: 1, pageSize: 0 }) },
    };

    render(
      <GeneratePage
        client={api as never}
        jobPoll={async (): Promise<JobSnapshot> => ({
          status: "running",
          progress: 40,
          message: "生成 3/6 篇摘要",
        })}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "开始生成" }));

    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(screen.getByRole("button", { name: /生成中/ })).toBeDisabled();
    expect(await screen.findByText(/生成 3\/6 篇摘要/)).toBeInTheDocument();
  });

  test("成功后回调 onDone 并带上最新一期 id", async () => {
    const onDone = vi.fn();
    const api = {
      settings: { get: async () => settings },
      issues: {
        create: async () => ({ jobId: "j1" }),
        list: async () => ({ items: [issue("i9")], total: 1, page: 1, pageSize: 1 }),
      },
    };

    render(
      <GeneratePage
        client={api as never}
        onDone={onDone}
        jobPoll={async (): Promise<JobSnapshot> => ({ status: "succeeded", progress: 100, message: "" })}
      />,
    );

    fireEvent.click(await screen.findByRole("button", { name: "开始生成" }));

    await waitFor(() => expect(onDone).toHaveBeenCalledWith("i9"));
  });

  test("没有 key 时提示去设置而不是干等", async () => {
    const api = {
      settings: { get: async () => ({ ...settings, apiKey: "", apiKeyMasked: false }) },
      issues: {
        create: async () => {
          throw Object.assign(new Error("未配置模型 API key"), { code: "NO_API_KEY" });
        },
        list: async () => ({ items: [], total: 0, page: 1, pageSize: 0 }),
      },
    };

    render(<GeneratePage client={api as never} jobPoll={async (): Promise<JobSnapshot> => ({ status: "succeeded", progress: 100, message: "" })} />);

    fireEvent.click(await screen.findByRole("button", { name: "开始生成" }));

    expect(await screen.findByText(/未配置模型 API key/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "去设置" })).toHaveAttribute("href", "/setup");
  });

  test("按分享时长算出目标字数", async () => {
    const api = {
      settings: { get: async () => settings },
      issues: { create: vi.fn(), list: async () => ({ items: [], total: 0, page: 1, pageSize: 0 }) },
    };

    render(<GeneratePage client={api as never} />);

    expect(await screen.findByText(/9000 字/)).toBeInTheDocument();
  });
});
