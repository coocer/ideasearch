import { ApiError, createClient } from "./client";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });

test("把 error 信封转成 ApiError", async () => {
  const fake = async () =>
    jsonResponse(
      {
        error: {
          code: "ISSUE_FAILED",
          message: "这期生成失败",
          details: { reason: "成功摘要 2 篇" },
        },
      },
      409,
    );
  const api = createClient(fake as unknown as typeof fetch);

  await expect(api.issues.detail("i1")).rejects.toMatchObject({
    status: 409,
    code: "ISSUE_FAILED",
    message: "这期生成失败",
  });
});

test("ApiError 是 Error 的子类，便于统一捕获", () => {
  const err = new ApiError(500, "X", "boom", { a: 1 });
  expect(err).toBeInstanceOf(Error);
  expect(err.details).toEqual({ a: 1 });
});

test("成功时返回解析后的 JSON", async () => {
  const fake = async () => jsonResponse({ items: [] });
  const api = createClient(fake as unknown as typeof fetch);
  expect(await api.topics.list()).toEqual({ items: [] });
});

test("POST 发送 JSON 方法正确", async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fake = async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    return jsonResponse({ jobId: "j1" }, 202);
  };
  const api = createClient(fake as unknown as typeof fetch);
  await api.issues.create();
  expect(calls[0].url).toBe("/api/v1/issues");
  expect(calls[0].init?.method).toBe("POST");
});

test("导出返回纯文本而不是 JSON", async () => {
  const fake = async () =>
    new Response("# 标题\n", { status: 200, headers: { "content-type": "text/markdown" } });
  const api = createClient(fake as unknown as typeof fetch);
  expect(await api.issues.export("i1")).toBe("# 标题\n");
});
