import { useEffect, useState } from "react";

import type { Client } from "../api/client";
import { useClient } from "../api/context";
import type { JobSnapshot, ReproPlan } from "../api/types";
import { useJob } from "../hooks/useJob";

interface Props {
  client?: Client;
  paperId: string;
  jobPoll?: (id: string) => Promise<JobSnapshot>;
}

const LEVEL_LABEL: Record<string, string> = {
  code_available: "有开源代码",
  partial: "部分线索",
  none: "无开源线索",
};

const fmt = (n: number | undefined) =>
  typeof n === "number" && Number.isFinite(n) ? n.toLocaleString("en-US") : "?";

export default function ReproPanel({ client: injected, paperId, jobPoll }: Props) {
  const client = useClient(injected);
  const fetchJob = jobPoll ?? ((id: string) => client.jobs.get(id));

  const [plan, setPlan] = useState<ReproPlan | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const job = useJob(jobId, { fetchJob });

  const load = async () => {
    try {
      const detail = await client.papers.detail(paperId);
      setPlan(detail.reproPlan);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [client, paperId]);

  useEffect(() => {
    if (job.status !== "succeeded" || !jobId) return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.status, jobId]);

  const start = async () => {
    if (starting || jobId) return;
    setStarting(true);
    setError("");
    try {
      const created = await client.papers.reproPlan(paperId);
      setJobId(created.jobId);
    } catch (e) {
      setError((e as Error).message);
      setStarting(false);
    }
  };

  const copyPrompt = async () => {
    const text = plan?.evidence?.handoff_prompt ?? "";
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setError("复制失败，请手动选择文本");
    }
  };

  const evidence = plan?.evidence;
  const estimate = plan?.estimate;

  return (
    <section className="repro">
      <h2>复现方案</h2>

      {error ? <p className="notice">{error}</p> : null}

      {!plan ? (
        <>
          <p className="hint">
            先给方案，你自己拿去交给 Claude / Codex 执行——系统不会跑论文代码。
          </p>
          <button
            type="button"
            className="btn"
            onClick={() => void start()}
            disabled={starting || jobId !== null}
          >
            {jobId ? "生成中…" : "生成复现方案"}
          </button>
          {jobId ? <p className="muted">{job.message || "已提交"}</p> : null}
        </>
      ) : (
        <>
          <dl className="kv">
            <dt>证据</dt>
            <dd>
              {LEVEL_LABEL[evidence?.level ?? ""] ?? evidence?.level ?? "未知"}
              {evidence?.note ? ` · ${evidence.note}` : ""}
            </dd>
            <dt>可复现性</dt>
            <dd>{evidence?.likelihood ?? "未知"}</dd>
            <dt>AI 协作成本</dt>
            <dd>
              {fmt(estimate?.token_range?.[0])} ~ {fmt(estimate?.token_range?.[1])} token
              （按你的模型单价换算）
            </dd>
            <dt>人力时间</dt>
            <dd>
              {fmt(estimate?.time_range_days?.[0])} ~ {fmt(estimate?.time_range_days?.[1])} 人天
            </dd>
            <dt>估不准的地方</dt>
            <dd>
              {evidence?.missing && evidence.missing.length > 0 ? (
                <ul className="plain-list">
                  {evidence.missing.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : (
                "—"
              )}
            </dd>
          </dl>

          {plan.planMd ? (
            <pre className="repro-plan">{plan.planMd}</pre>
          ) : null}

          {evidence?.handoff_prompt ? (
            <pre className="handoff">{evidence.handoff_prompt}</pre>
          ) : null}

          <div className="actions">
            <button type="button" className="btn small" onClick={() => void copyPrompt()}>
              {copied ? "已复制" : "复制提示词"}
            </button>
            <button type="button" className="btn small" onClick={() => void start()}>
              重新生成
            </button>
          </div>
        </>
      )}
    </section>
  );
}
