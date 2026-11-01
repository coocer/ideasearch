import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import type { Source } from "../api/types";
import SourcesPage from "./SourcesPage";

const page = (items: Source[]) => ({ items, total: items.length, page: 1, pageSize: items.length });

const source = (over: Partial<Source>): Source => ({
  id: 1,
  kind: "rss",
  name: "量子位",
  url: "https://example.test/feed",
  config: {},
  weight: 1,
  enabled: true,
  ...over,
});

describe("SourcesPage", () => {
  test("三类来源分组渲染", async () => {
    const api = {
      sources: {
        list: async () =>
          page([
            source({ id: 1, kind: "search", name: "DeepSeek Search", url: "" }),
            source({ id: 2, kind: "arxiv", name: "arXiv", url: "", config: { categories: ["cs.LG"] } }),
            source({ id: 3, kind: "rss", name: "量子位" }),
          ]),
        create: vi.fn(),
        patch: vi.fn(),
        remove: vi.fn(),
      },
    };

    render(<SourcesPage client={api as never} />);

    expect(await screen.findByRole("heading", { name: "Web Search" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "arXiv" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "RSS 源" })).toBeInTheDocument();
  });

  test("添加 RSS 源带上 kind", async () => {
    const create = vi.fn(async (_body: Partial<Source>) => source({}));
    const api = {
      sources: { list: async () => page([]), create, patch: vi.fn(), remove: vi.fn() },
    };

    render(<SourcesPage client={api as never} />);

    fireEvent.change(await screen.findByLabelText("名称"), { target: { value: "量子位" } });
    fireEvent.change(screen.getByLabelText("RSS 地址"), { target: { value: "https://x/feed" } });
    fireEvent.click(screen.getByRole("button", { name: "添加源" }));

    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).toMatchObject({
      kind: "rss",
      name: "量子位",
      url: "https://x/feed",
    });
  });

  test("停用调用 remove", async () => {
    const remove = vi.fn(async (_id: number) => undefined);
    const api = {
      sources: { list: async () => page([source({})]), create: vi.fn(), patch: vi.fn(), remove },
    };

    render(<SourcesPage client={api as never} />);
    fireEvent.click(await screen.findByRole("button", { name: "停用" }));

    await waitFor(() => expect(remove).toHaveBeenCalledWith(1));
  });

  test("空库时 Web Search 段给出「只开这个也能用」的说明", async () => {
    const api = {
      sources: { list: async () => page([]), create: vi.fn(), patch: vi.fn(), remove: vi.fn() },
    };

    render(<SourcesPage client={api as never} />);
    expect(await screen.findByText(/只开 Web Search 也能用/)).toBeInTheDocument();
  });
});
