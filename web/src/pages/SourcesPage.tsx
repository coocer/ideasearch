import { useCallback, useEffect, useState } from "react";

import type { Client } from "../api/client";
import { useClient } from "../api/context";
import type { Source } from "../api/types";
import { TextField } from "../components/Field";

const KIND_LABEL: Record<Source["kind"], string> = {
  search: "Web Search",
  arxiv: "arXiv",
  rss: "RSS 源",
};

const KIND_HINT: Record<Source["kind"], string> = {
  search: "只开 Web Search 也能用：它按研究方向的关键词自动搜网页，不需要你挑站点。",
  arxiv: "按分类抓预印本，适合 CS / 物理 / 数学这类领域。",
  rss: "适合固定追几家媒体或竞品博客；跨学科场景可以一个都不配。",
};

export default function SourcesPage({ client: injected }: { client?: Client } = {}) {
  const client = useClient(injected);

  const [items, setItems] = useState<Source[] | null>(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState({ name: "", url: "" });

  const load = useCallback(async () => {
    try {
      const page = await client.sources.list();
      setItems(page.items);
    } catch (e) {
      setError((e as Error).message);
      setItems([]);
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const addRss = async () => {
    setError("");
    if (!draft.name.trim() || !draft.url.trim()) {
      setError("名称和 RSS 地址都要填");
      return;
    }
    try {
      await client.sources.create({
        kind: "rss",
        name: draft.name.trim(),
        url: draft.url.trim(),
        config: { feed_kind: "industry" },
        weight: 1,
      });
      setDraft({ name: "", url: "" });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const disable = async (id: number) => {
    setError("");
    try {
      await client.sources.remove(id);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const rowsFor = (kind: Source["kind"]) => (items ?? []).filter((s) => s.kind === kind);

  const renderRows = (kind: Source["kind"]) => {
    const rows = rowsFor(kind);
    if (items === null) return <p className="muted">正在读取…</p>;
    if (rows.length === 0) return <p className="muted">还没有配置。</p>;
    return (
      <div className="list">
        {rows.map((row) => {
          const categories = (row.config?.categories as string[] | undefined) ?? [];
          return (
            <div className="list-row" key={row.id}>
              <div>
                <div className="row-title">{row.name}</div>
                <div className="muted">{row.enabled ? "启用" : "停用"}</div>
              </div>
              <div>
                {categories.map((c) => (
                  <span className="chip" key={c}>
                    {c}
                  </span>
                ))}
                {row.url ? <span className="muted">{row.url}</span> : null}
              </div>
              <div className="row-actions">
                {row.enabled ? (
                  <button type="button" className="btn small" onClick={() => void disable(row.id)}>
                    停用
                  </button>
                ) : (
                  <span className="badge">已停用</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div>
      <div className="screen-head">
        <h1>数据源</h1>
        <p>三种来源可以只开一种。跨学科的人通常只开 Web Search 就够了。</p>
      </div>

      {error ? <p className="notice">{error}</p> : null}

      {(["search", "arxiv", "rss"] as const).map((kind) => (
        <section className="block" key={kind}>
          <h2>{KIND_LABEL[kind]}</h2>
          <p className="hint">{KIND_HINT[kind]}</p>
          {renderRows(kind)}
          {kind === "rss" ? (
            <div className="row2" style={{ marginTop: 16 }}>
              <TextField
                label="名称"
                value={draft.name}
                onChange={(v) => setDraft({ ...draft, name: v })}
              />
              <TextField
                label="RSS 地址"
                value={draft.url}
                onChange={(v) => setDraft({ ...draft, url: v })}
              />
            </div>
          ) : null}
          {kind === "rss" ? (
            <div className="actions">
              <button type="button" className="btn" onClick={() => void addRss()}>
                添加源
              </button>
            </div>
          ) : null}
        </section>
      ))}
    </div>
  );
}
