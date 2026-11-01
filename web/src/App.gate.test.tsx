import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { expect, test } from "vitest";

import App from "./App";
import { ClientProvider } from "./api/context";

const settings = (over: Record<string, unknown> = {}) => ({
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
  ...over,
});

const renderApp = (client: unknown, path = "/") =>
  render(
    <ClientProvider client={client as never}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </ClientProvider>,
  );

test("没有 key 时自动跳到设置页", async () => {
  renderApp({
    settings: { get: async () => settings({ apiKey: "", apiKeyMasked: false }), update: async () => settings(), test: async () => ({ ok: false }) },
    issues: { list: async () => ({ items: [], total: 0, page: 1, pageSize: 0 }) },
  });

  expect(await screen.findByRole("heading", { name: "设置" })).toBeInTheDocument();
});

test("已配置 key 时停在原页面", async () => {
  renderApp({
    settings: { get: async () => settings(), update: async () => settings(), test: async () => ({ ok: true }) },
    issues: { list: async () => ({ items: [], total: 0, page: 1, pageSize: 0 }) },
  });

  expect(await screen.findByRole("heading", { name: "本期文章" })).toBeInTheDocument();
});
