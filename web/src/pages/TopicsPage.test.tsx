import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";

import type { Topic } from "../api/types";
import TopicsPage from "./TopicsPage";

const page = (items: Topic[]) => ({ items, total: items.length, page: 1, pageSize: items.length });

const topic = (over: Partial<Topic> = {}): Topic => ({
  id: 1,
  key: "inference",
  label: "推理优化",
  keywords: ["kv cache"],
  weight: 1,
  enabled: true,
  ...over,
});

describe("TopicsPage", () => {
  test("切换权重调用 patch", async () => {
    const patch = vi.fn(async () => topic());
    const api = {
      topics: { list: async () => page([topic()]), create: vi.fn(), patch, remove: vi.fn() },
    };

    render(<TopicsPage client={api as never} />);
    fireEvent.click(await screen.findByRole("button", { name: "权重 3" }));

    await waitFor(() => expect(patch).toHaveBeenCalledWith("inference", { weight: 3 }));
  });

  test("新建方向把关键词拆成数组", async () => {
    const create = vi.fn(async (_body: Partial<Topic>) => topic({ key: "hw" }));
    const api = {
      topics: { list: async () => page([]), create, patch: vi.fn(), remove: vi.fn() },
    };

    render(<TopicsPage client={api as never} />);

    fireEvent.change(await screen.findByLabelText("key"), { target: { value: "hw" } });
    fireEvent.change(screen.getByLabelText("显示名"), { target: { value: "硬件动态" } });
    fireEvent.change(screen.getByLabelText("关键词（逗号分隔）"), {
      target: { value: "hbm, gpu , nvl72" },
    });
    fireEvent.click(screen.getByRole("button", { name: "添加方向" }));

    await waitFor(() => expect(create).toHaveBeenCalled());
    expect(create.mock.calls[0][0]).toMatchObject({
      key: "hw",
      label: "硬件动态",
      keywords: ["hbm", "gpu", "nvl72"],
    });
  });

  test("key 冲突时把后端消息显示出来", async () => {
    const create = vi.fn(async () => {
      throw Object.assign(new Error("该方向 key 已存在"), { code: "TOPIC_KEY_CONFLICT" });
    });
    const api = {
      topics: { list: async () => page([]), create, patch: vi.fn(), remove: vi.fn() },
    };

    render(<TopicsPage client={api as never} />);

    fireEvent.change(await screen.findByLabelText("key"), { target: { value: "dup" } });
    fireEvent.change(screen.getByLabelText("显示名"), { target: { value: "X" } });
    fireEvent.click(screen.getByRole("button", { name: "添加方向" }));

    expect(await screen.findByText(/该方向 key 已存在/)).toBeInTheDocument();
  });

  test("停用调用 remove", async () => {
    const remove = vi.fn(async () => undefined);
    const api = {
      topics: { list: async () => page([topic()]), create: vi.fn(), patch: vi.fn(), remove },
    };

    render(<TopicsPage client={api as never} />);
    fireEvent.click(await screen.findByRole("button", { name: "停用" }));

    await waitFor(() => expect(remove).toHaveBeenCalledWith("inference"));
  });
});
