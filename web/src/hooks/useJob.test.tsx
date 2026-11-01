import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, test } from "vitest";

import { useJob } from "./useJob";

describe("useJob", () => {
  test("轮询到 succeeded 就停", async () => {
    let calls = 0;
    const fetchJob = async () => ({
      status: ++calls < 2 ? "running" : "succeeded",
      progress: 50,
      message: "",
    });

    const { result } = renderHook(() =>
      useJob("j1", { fetchJob, intervalMs: 5 }),
    );

    await waitFor(() => expect(result.current.status).toBe("succeeded"));
    expect(calls).toBe(2);
  });

  test("job 失败时停止轮询并带上错误", async () => {
    let calls = 0;
    const fetchJob = async () => {
      calls += 1;
      return { status: "failed", progress: 0, message: "", error: "boom" };
    };

    const { result } = renderHook(() =>
      useJob("j1", { fetchJob, intervalMs: 5 }),
    );

    await waitFor(() => expect(result.current.status).toBe("failed"));
    expect(result.current.error).toBe("boom");
    expect(calls).toBe(1);
  });

  test("轮询抛错时停止并报错，不无限重试", async () => {
    let calls = 0;
    const fetchJob = async () => {
      calls += 1;
      throw new Error("network down");
    };

    const { result } = renderHook(() =>
      useJob("j1", { fetchJob, intervalMs: 5 }),
    );

    await waitFor(() => expect(result.current.status).toBe("failed"));
    expect(calls).toBe(1);
    expect(result.current.error).toContain("network down");
  });

  test("没有 jobId 时不轮询", async () => {
    let calls = 0;
    const fetchJob = async () => {
      calls += 1;
      return { status: "succeeded", progress: 100, message: "" };
    };

    const { result } = renderHook(() => useJob(null, { fetchJob, intervalMs: 5 }));

    await new Promise((r) => setTimeout(r, 30));
    expect(calls).toBe(0);
    expect(result.current.status).toBe("idle");
  });
});
