import { useCallback, useEffect, useState } from "react";

import type { Client } from "../api/client";
import { useClient } from "../api/context";
import type { Topic } from "../api/types";
import { TextField } from "../components/Field";

export default function TopicsPage({ client: injected }: { client?: Client } = {}) {
  const client = useClient(injected);

  const [items, setItems] = useState<Topic[] | null>(null);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState({ key: "", label: "", keywords: "" });

  const load = useCallback(async () => {
    try {
      const page = await client.topics.list();
      setItems(page.items);
    } catch (e) {
      setError((e as Error).message);
      setItems([]);
    }
  }, [client]);

  useEffect(() => {
    void load();
  }, [load]);

  const add = async () => {
    setError("");
    const key = draft.key.trim();
    if (!key) {
      setError("key 不能为空");
      return;
    }
    try {
      await client.topics.create({
        key,
        label: draft.label.trim() || key,
        keywords: draft.keywords
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        weight: 1,
      });
      setDraft({ key: "", label: "", keywords: "" });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const setWeight = async (key: string, weight: number) => {
    setError("");
    try {
      await client.topics.patch(key, { weight });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const disable = async (key: string) => {
    setError("");
    try {
      await client.topics.remove(key);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div>
      <div className="screen-head">
        <h1>研究方向</h1>
        <p>方向决定抓什么、怎么排序。权重会真实影响选材——权重高的方向更容易占满名额。</p>
      </div>

      {error ? <p className="notice">{error}</p> : null}

      <section className="block">
        <h2>已有方向</h2>
        {items === null ? (
          <p className="muted">正在读取…</p>
        ) : items.length === 0 ? (
          <p className="muted">还没有方向。先在下面加一个。</p>
        ) : (
          <div className="list">
            {items.map((topic) => (
              <div className="list-row" key={topic.key}>
                <div>
                  <div className="row-title">{topic.label}</div>
                  <div className="muted">{topic.key}</div>
                </div>
                <div>
                  {topic.keywords.map((kw) => (
                    <span className="chip" key={kw}>
                      {kw}
                    </span>
                  ))}
                </div>
                <div className="row-actions">
                  <div className="seg" role="group" aria-label={`${topic.label} 权重`}>
                    {[1, 2, 3].map((weight) => (
                      <button
                        key={weight}
                        type="button"
                        aria-label={`权重 ${weight}`}
                        aria-pressed={topic.weight === weight}
                        onClick={() => void setWeight(topic.key, weight)}
                      >
                        {weight}
                      </button>
                    ))}
                  </div>
                  <span className={`badge ${topic.enabled ? "ok" : ""}`}>
                    {topic.enabled ? "启用" : "停用"}
                  </span>
                  {topic.enabled ? (
                    <button type="button" className="btn small" onClick={() => void disable(topic.key)}>
                      停用
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="block">
        <h2>添加方向</h2>
        <div className="row3">
          <TextField label="key" value={draft.key} onChange={(v) => setDraft({ ...draft, key: v })} hint="稳定标识，建后不可改" />
          <TextField label="显示名" value={draft.label} onChange={(v) => setDraft({ ...draft, label: v })} />
          <TextField
            label="关键词（逗号分隔）"
            value={draft.keywords}
            onChange={(v) => setDraft({ ...draft, keywords: v })}
            hint="用于检索与打分"
          />
        </div>
        <div className="actions">
          <button type="button" className="btn primary" onClick={() => void add()}>
            添加方向
          </button>
        </div>
      </section>
    </div>
  );
}
