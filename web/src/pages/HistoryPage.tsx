import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import type { Client } from "../api/client";
import { useClient } from "../api/context";
import type { IssueListItem } from "../api/types";

export default function HistoryPage({ client: injected }: { client?: Client } = {}) {
  const client = useClient(injected);
  const [items, setItems] = useState<IssueListItem[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    client.issues
      .list()
      .then((page) => {
        if (!cancelled) setItems(page.items);
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e.message);
          setItems([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  return (
    <div>
      <div className="screen-head">
        <h1>历史文章</h1>
        <p>每期都保存当时的配置快照，所以后的方向调整不会影响旧文章的解释。</p>
      </div>

      {error ? <p className="notice">{error}</p> : null}

      {items === null ? (
        <p className="muted">正在读取…</p>
      ) : items.length === 0 ? (
        <p>
          还没有任何一期。<Link to="/generate" className="btn primary">去生成第一期</Link>
        </p>
      ) : (
        <div className="list">
          {items.map((item) => (
            <div className="list-row" key={item.id}>
              <div>
                <div className="row-title">{item.title}</div>
                <div className="muted">{item.createdAt.slice(0, 10)}</div>
              </div>
              <div className="muted">
                最近 {item.windowDays} 天 · 目标 {item.targetWords} 字
              </div>
              <div className="row-actions">
                {item.status === "failed" ? <span className="badge">失败</span> : null}
                <Link className="btn small" to={`/issues/${item.id}`}>
                  查看
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
