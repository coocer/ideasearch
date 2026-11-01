import type {
  IssueDetail,
  IssueListItem,
  JobSnapshot,
  Page,
  PaperDetail,
  SettingsView,
  Source,
  Topic,
} from "./types";

export class ApiError extends Error {
  status: number;
  code: string;
  details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

const SETTINGS_FROM_API: Record<string, string> = {
  llm_base_url: "baseUrl",
  llm_model: "model",
  llm_api_key: "apiKey",
  api_key_masked: "apiKeyMasked",
  window_days: "windowDays",
  background_json: "background",
  title: "title",
  share_minutes: "shareMinutes",
  words_per_minute: "wordsPerMinute",
  min_papers: "minPapers",
  max_papers: "maxPapers",
};

const SETTINGS_TO_API: Record<string, string> = Object.fromEntries(
  Object.entries(SETTINGS_FROM_API).map(([api, view]) => [view, api]),
);

function normalizeSettings(raw: Record<string, unknown>): SettingsView {
  const out: Record<string, unknown> = {};
  for (const [api, view] of Object.entries(SETTINGS_FROM_API)) {
    if (api in raw) out[view] = raw[api];
  }
  if (typeof out.background === "string") {
    try {
      out.background = JSON.parse(out.background as string);
    } catch {
      out.background = {};
    }
  }
  return {
    baseUrl: "",
    model: "",
    apiKey: "",
    apiKeyMasked: true,
    windowDays: 7,
    background: {},
    title: "",
    shareMinutes: 60,
    wordsPerMinute: 150,
    minPapers: 5,
    maxPapers: 10,
    ...out,
  } as SettingsView;
}

function denormalizeSettings(patch: Partial<SettingsView>): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(patch)) {
    const api = SETTINGS_TO_API[key];
    if (api) out[api] = value;
  }
  return out;
}

export function createClient(fetchImpl?: typeof fetch) {
  const doFetch: typeof fetch = fetchImpl ?? ((...args) => globalThis.fetch(...args));

  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await doFetch(`/api/v1${path}`, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
    const text = await response.text();
    const body = text ? JSON.parse(text) : null;

    if (!response.ok) {
      const envelope = (body as { error?: { code?: string; message?: string; details?: unknown } })?.error;
      throw new ApiError(
        response.status,
        envelope?.code ?? "HTTP_ERROR",
        envelope?.message ?? `请求失败（HTTP ${response.status}）`,
        (envelope?.details as Record<string, unknown>) ?? {},
      );
    }
    return body as T;
  }

  async function requestText(path: string): Promise<string> {
    const response = await doFetch(`/api/v1${path}`);
    if (!response.ok) {
      const text = await response.text();
      const envelope = text ? (JSON.parse(text) as { error?: { code?: string; message?: string } })?.error : null;
      throw new ApiError(
        response.status,
        envelope?.code ?? "HTTP_ERROR",
        envelope?.message ?? `请求失败（HTTP ${response.status}）`,
      );
    }
    return response.text();
  }

  return {
    settings: {
      get: async () => normalizeSettings(await request<Record<string, unknown>>("/settings")),
      update: async (patch: Partial<SettingsView>) => {
        const body: Record<string, unknown> = denormalizeSettings(patch);
        // 背景以对象提交，后端负责序列化
        if (patch.background) body.background_json = patch.background;
        return normalizeSettings(await request<Record<string, unknown>>("/settings", {
          method: "PUT",
          body: JSON.stringify(body),
        }));
      },
      test: () => request<{ ok: boolean; model?: string; hasKey?: boolean }>("/settings/test", { method: "POST" }),
    },

    topics: {
      list: () => request<Page<Topic>>("/topics"),
      create: (body: Partial<Topic>) => request<Topic>("/topics", { method: "POST", body: JSON.stringify(body) }),
      patch: (key: string, body: Partial<Topic>) =>
        request<Topic>(`/topics/${encodeURIComponent(key)}`, { method: "PATCH", body: JSON.stringify(body) }),
      remove: (key: string) => request<void>(`/topics/${encodeURIComponent(key)}`, { method: "DELETE" }),
    },

    sources: {
      list: () => request<Page<Source>>("/sources"),
      create: (body: Partial<Source>) => request<Source>("/sources", { method: "POST", body: JSON.stringify(body) }),
      patch: (id: number, body: Partial<Source>) =>
        request<Source>(`/sources/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
      remove: (id: number) => request<void>(`/sources/${id}`, { method: "DELETE" }),
    },

    issues: {
      list: () => request<Page<IssueListItem>>("/issues"),
      create: () => request<{ jobId: string }>("/issues", { method: "POST" }),
      detail: (id: string) => request<IssueDetail>(`/issues/${encodeURIComponent(id)}`),
      remove: (id: string) => request<void>(`/issues/${encodeURIComponent(id)}`, { method: "DELETE" }),
      export: (id: string) => requestText(`/issues/${encodeURIComponent(id)}/export`),
    },

    papers: {
      detail: (id: string) => request<PaperDetail>(`/papers/${encodeURIComponent(id)}`),
      deepRead: (id: string) =>
        request<{ jobId: string; cached: boolean }>(`/papers/${encodeURIComponent(id)}/deep-read`, { method: "POST" }),
      reproPlan: (id: string) =>
        request<{ jobId: string; cached: boolean }>(`/papers/${encodeURIComponent(id)}/repro-plan`, { method: "POST" }),
    },

    jobs: {
      get: (id: string) => request<JobSnapshot>(`/jobs/${encodeURIComponent(id)}`),
    },
  };
}

export type Client = ReturnType<typeof createClient>;
