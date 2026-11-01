import { useEffect, useState } from "react";

import type { Client } from "../api/client";
import { useClient } from "../api/context";
import type { JobSnapshot, SettingsView } from "../api/types";
import { ProgressBar } from "../components/Loading";
import { useJob } from "../hooks/useJob";

interface Props {
  client?: Client;
  jobPoll?: (id: string) => Promise<JobSnapshot>;
  onDone?: (issueId: string) => void;
}

export default function GeneratePage({ client: injected, jobPoll, onDone }: Props = {}) {
  const client = useClient(injected);
  // 用箭头包一层：client 可能没有 jobs（测试桩），只有轮询真正发生时才访问
  const fetchJob = jobPoll ?? ((id: string) => client.jobs.get(id));

  const [settings, setSettings] = useState<SettingsView | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const job = useJob(jobId, { fetchJob });

  useEffect(() => {
    let cancelled = false;
    client.settings
      .get()
      .then((value) => {
        if (!cancelled) setSettings(value);
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message);
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  useEffect(() => {
    if (job.status !== "succeeded" || !jobId) return;
    let cancelled = false;
    client.issues
      .list()
      .then((page) => {
        const latest = page.items[0];
        if (!cancelled && latest) onDone?.(latest.id);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [job.status, jobId, client, onDone]);

  const start = async () => {
    setError("");
    setStarting(true);
    try {
      const created = await client.issues.create();
      setJobId(created.jobId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setStarting(false);
    }
  };

  if (!settings) {
    return (
      <div>
        <div className="screen-head">
          <h1>生成新一期</h1>
        </div>
        <p className="muted">{error || "正在读取配置…"}</p>
      </div>
    );
  }

  const targetWords = settings.shareMinutes * settings.wordsPerMinute;

  return (
    <div>
      <div className="screen-head">
        <h1>生成新一期</h1>
        <p>抓取窗口内的论文与动态，按方向排序后逐篇生成摘要。深读与复现方案不在此步生成。</p>
      </div>

      {error ? (
        <p className="notice">
          {error}
          <a className="btn small" href="/setup" style={{ marginLeft: 12 }}>
            去设置
          </a>
        </p>
      ) : null}

      <section className="block">
        <h2>这次会做什么</h2>
        <p className="hint">
          抓最近 {settings.windowDays} 天的内容；目标篇幅约 {targetWords} 字（
          {settings.shareMinutes} 分钟 × {settings.wordsPerMinute} 字/分钟）。
        </p>
        <ul className="plain-list">
          <li>按研究方向检索论文与行业动态</li>
          <li>逐篇生成四段式摘要，失败的那篇会排出而不是写占位</li>
          <li>成功篇数不足 {settings.minPapers} 篇时整期作废，不给你半成品</li>
        </ul>
        <div className="actions">
          <button
            type="button"
            className="btn primary"
            onClick={() => void start()}
            disabled={starting || jobId !== null}
          >
            {jobId ? "生成中…" : "开始生成"}
          </button>
        </div>
      </section>

      {jobId ? (
        <section className="block">
          <h2>进度</h2>
          <ProgressBar percent={job.progress} label={job.message || "已提交，等待开始"} />
          {job.status === "failed" ? <p className="notice">生成失败：{job.error}</p> : null}
          {job.status === "timeout" ? (
            <p className="notice">等太久了，可能卡在模型调用上。可以稍后到历史里看结果。</p>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}
