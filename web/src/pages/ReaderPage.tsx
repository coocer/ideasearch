import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { Client } from "../api/client";
import { useClient } from "../api/context";
import type { DeepRead, JobSnapshot, PaperDetail } from "../api/types";
import Gauge from "../components/Gauge";
import { useJob } from "../hooks/useJob";

interface Props {
  client?: Client;
  paperId?: string;
  jobPoll?: (id: string) => Promise<JobSnapshot>;
}

export default function ReaderPage({ client: injected, paperId, jobPoll }: Props = {}) {
  const client = useClient(injected);
  const fetchJob = jobPoll ?? ((id: string) => client.jobs.get(id));

  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState(0);

  const job = useJob(jobId, { fetchJob });

  const load = async () => {
    if (!paperId) return;
    try {
      setPaper(await client.papers.detail(paperId));
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

  useEffect(() => {
    const onScroll = () => {
      const doc = document.documentElement;
      const max = doc.scrollHeight - window.innerHeight;
      setProgress(max > 0 ? Math.min(100, (window.scrollY / max) * 100) : 0);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const startDeepRead = async () => {
    if (!paperId || starting || jobId) return;
    setStarting(true);
    setError("");
    try {
      const created = await client.papers.deepRead(paperId);
      setJobId(created.jobId);
    } catch (e) {
      setError((e as Error).message);
      setStarting(false);
    }
  };

  if (!paperId) {
    return (
      <div className="reader">
        <p className="muted">没有指定论文。</p>
        <Link to="/" className="btn">
          返回
        </Link>
      </div>
    );
  }

  const deep: DeepRead | null = paper?.deepRead ?? null;
  const abstractOnly =
    paper?.fulltextStatus === "abstract_only" || deep?.fulltext_status === "abstract_only";

  return (
    <div className="reader">
      <div
        className="reader-progress"
        role="progressbar"
        aria-label="阅读进度"
        aria-valuenow={Math.round(progress)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div style={{ width: `${progress}%` }} />
      </div>

      <div className="reader-topbar">
        <Link to="/" className="btn small">
          ← 返回文章
        </Link>
        <span className="muted">{paper?.title ?? "正在读取…"}</span>
      </div>

      {error ? <p className="notice">{error}</p> : null}

      {!paper ? (
        <p className="muted">正在读取…</p>
      ) : deep ? (
        <article className="reader-body">
          <p className="muted">{abstractOnly ? "仅基于摘要，未拿到全文" : "基于全文"}</p>

          <h1>{paper.title}</h1>

          <section>
            <h2>为什么值得看</h2>
            <p>{deep.why_it_matters}</p>
          </section>

          <section>
            <h2>读懂它需要的前置</h2>
            <p>{deep.background}</p>
          </section>

          <section>
            <h2>他们做了什么</h2>
            <p>{deep.what_they_did}</p>
          </section>

          <section>
            <h2>为什么这样有效</h2>
            <p>{deep.why_it_works}</p>
          </section>

          <section>
            <h2>边界与没说的代价</h2>
            <p>{deep.limits}</p>
          </section>

          <section className="reader-value">
            <h2>对你的价值</h2>
            <p>{deep.value_for_you}</p>
          </section>

          <footer className="reader-foot">
            {deep.verdict ? <Gauge level={deep.verdict} /> : null}
            {deep.jargon && deep.jargon.length > 0 ? (
              <dl className="glossary">
                {deep.jargon.map(([term, meaning]) => (
                  <div key={term}>
                    <dt>{term}</dt>
                    <dd>{meaning}</dd>
                  </div>
                ))}
              </dl>
            ) : null}
          </footer>
        </article>
      ) : (
        <div className="reader-gate">
          <h1>{paper.title}</h1>
          <p className="muted">{abstractOnly ? "这篇只拿到了摘要。" : ""}</p>
          <button
            type="button"
            className="btn primary"
            onClick={() => void startDeepRead()}
            disabled={starting || jobId !== null}
          >
            {jobId ? "生成中…" : "开始深读"}
          </button>
          {jobId ? <p className="muted">{job.message || "已提交"}</p> : null}
          {job.status === "failed" ? <p className="notice">深读失败：{job.error}</p> : null}
        </div>
      )}
    </div>
  );
}
