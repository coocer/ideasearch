import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import type { SettingsView } from "../api/types";
import SetupPage from "./SetupPage";

const settings = (over: Record<string, unknown> = {}) => ({
  baseUrl: "https://api.deepseek.com",
  model: "deepseek-flash",
  apiKey: "sk-***",
  apiKeyMasked: true,
  windowDays: 7,
  background: { role: "推理工程师" },
  title: "周观察报告",
  shareMinutes: 60,
  wordsPerMinute: 150,
  minPapers: 5,
  maxPapers: 10,
  ...over,
});

describe("SetupPage", () => {
  test("回填打码后的 key，保存时不下发占位符", async () => {
    const update = vi.fn(async (_patch: Partial<SettingsView>) => settings());
    const api = {
      settings: { get: async () => settings(), update, test: async () => ({ ok: true }) },
    };

    render(<SetupPage client={api as never} />);

    const key = await screen.findByLabelText("API Key");
    expect(key).toHaveValue("sk-***");

    fireEvent.click(screen.getByRole("button", { name: "保存" }));

    await waitFor(() => expect(update).toHaveBeenCalled());
    expect(JSON.stringify(update.mock.calls[0][0])).not.toContain("sk-***");
  });

  test("没有 key 时提示还需要填写", async () => {
    const api = {
      settings: {
        get: async () => settings({ apiKey: "", apiKeyMasked: false }),
        update: async () => settings(),
        test: async () => ({ ok: false }),
      },
    };

    render(<SetupPage client={api as never} />);

    expect(await screen.findByText(/还需要填写 API Key/)).toBeInTheDocument();
  });

  test("有 key 时不显示未配置提示", async () => {
    const api = {
      settings: { get: async () => settings(), update: async () => settings(), test: async () => ({ ok: true }) },
    };

    render(<SetupPage client={api as never} />);

    await screen.findByLabelText("API Key");
    expect(screen.queryByText(/还需要填写 API Key/)).not.toBeInTheDocument();
  });

  test("测试连接显示结果", async () => {
    const api = {
      settings: {
        get: async () => settings(),
        update: async () => settings(),
        test: async () => ({ ok: true }),
      },
    };

    render(<SetupPage client={api as never} />);
    fireEvent.click(await screen.findByRole("button", { name: "测试连接" }));

    expect(await screen.findByText(/连接正常/)).toBeInTheDocument();
  });
});
