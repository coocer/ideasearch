import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError, type Client } from "../api/client";
import { useClient } from "../api/context";
import type { IssueDetail } from "../api/types";

interface Props {
  client?: Client;
  issueId?: string;
}

export default function IssuePage({ client: injected, issueId }: Props = {}) {
  const client = useClient(injected);

  const [issue, setIssue] = useState<IssueDetail | null>(null);
  const [error, setError] = useState<{ message: string; reason: string } | null>(null);
  const [openSummary, setOpenSummary] = useState<Record<string, boolean>>({});
  const [exportError, setExportError] = useState("");

  const downloadMarkdown = async (target: IssueDetail) => {
    setExportError("");
    try {
      const text = await client.issues.export(target.id);
      const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${target.title || "期号"}.md`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setExportError((e as Error).message);
    }
  };

  useEffect(() => {
    if (!issueId) return;
    let cancelled = false;
    client.issues
      .detail(issueId)
      .then((value) => {
        if (!cancelled) setIssue(value);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError) {
          const reason = typeof e.details.reason === "string" ? e.details.reason : "";
          setError({ message: e.message, reason });
        } else {
          setError({ message: (e as Error).message, reason: "" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [client, issueId]);

  if (!issueId) {
    return (
      <div>
        <div className="screen-head">
          <h1>本期文章</h1>
          <p>还没有打开某一期。</p>
        </div>
        <p>
          <Link to="/generate" className="btn primary">
            去生成第一期
          </Link>
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <div className="screen-head">
          <h1>本期文章</h1>
        </div>
        <p className="notice">
          {error.message}
          {error.reason ? (
            <>
              <br />
              {error.reason}
            </>
          ) : null}
        </p>
        <p>
          <Link to="/generate" className="btn">
            去生成新一期
          </Link>
        </p>
      </div>
    );
  }

  if (!issue) {
    return (
      <div>
        <div className="screen-head">
          <h1>本期文章</h1>
        </div>
        <p className="muted">正在读取…</p>
      </div>
    );
  }

  return (
    <div>
      <div className="screen-head">
        <h1>{issue.title}</h1>
        <p>
          {issue.papers.length} 篇论文 · 目标 {issue.targetWords} 字 · {issue.createdAt.slice(0, 10)}
        </p>
        <div className="actions" style={{ marginTop: 10 }}>
          <button type="button" className="btn small" onClick={() => void downloadMarkdown(issue)}>
            导出 Markdown
          </button>
          {exportError ? <span className="muted">{exportError}</span> : null}
        </div>
      </div>

      {issue.papers.map((paper, index) => {
        const open = openSummary[paper.id] ?? false;
        return (
          <article className="paper" key={paper.id}>
            <h2 className="paper-title">
              <a href={paper.url} target="_blank" rel="noreferrer">
                {index + 1}. {paper.title}
              </a>
            </h2>
            <p className="muted">{paper.topicKey}</p>
            <p className="oneline">
              <strong>一句话</strong>　{paper.oneLine}
            </p>
            <details className="four" open={open}>
              <summary
                onClick={(event) => {
                  event.preventDefault();
                  setOpenSummary((prev) => ({ ...prev, [paper.id]: !open }));
                }}
              >
                四段式摘要
              </summary>
              <div className="prose">
                <h3>核心解决的问题</h3>
                <p>{paper.summary.core_problem}</p>
                <h3>核心技术手段</h3>
                <p>{paper.summary.technique}</p>
                <h3>实际效果</h3>
                <p>{paper.summary.results}</p>
                <h3>后续计划与启发</h3>
                <p>{paper.summary.outlook}</p>
              </div>
            </details>
            <div className="actions">
              <Link className="btn small" to={`/read/${paper.id}`}>
                进入阅读模式
              </Link>
            </div>
          </article>
        );
      })}

      <section className="news">
        <h2>行业与竞品动态</h2>
        {issue.news.length === 0 ? (
          <p className="muted">本期没有抓到动态。</p>
        ) : (
          issue.news.map((item) => (
            <div className="news-row" key={`${item.source}-${item.title}`}>
              <div>
                <div className="news-title">{item.title}</div>
                <div className="muted">{item.detail || item.oneLine}</div>
              </div>
              <div className="muted">{item.source}</div>
            </div>
          ))
        )}
        <p className="muted">动态不提供深读与复现方案——它们不是可复现的研究。</p>
      </section>
    </div>
  );
}
