import { useEffect, useState } from "react";

import type { Client } from "../api/client";
import { useClient } from "../api/context";
import type { SettingsView } from "../api/types";
import { SecretField, TextAreaField, TextField } from "../components/Field";

const MASK = "sk-***";

const BACKGROUND_FIELDS: Array<[keyof NonNullable<SettingsView["background"]>, string, string]> = [
  ["role", "角色", "例如：推理平台工程师"],
  ["current_work", "当前在做的系统", "一到三条，越具体，深读的价值判断越具体"],
  ["bottlenecks", "现在的瓶颈", "性能、成本还是效果？最好带上具体数字"],
  ["stack", "技术栈与环境", "决定方案能不能落到你手上"],
  ["near_term_goals", "半年内目标", "决定「值不值得投入」的时间尺度"],
  ["non_interests", "明确不关心的方向", "抑制「什么都值得关注」的废话"],
];

export default function SetupPage({ client: injected }: { client?: Client } = {}) {
  const client = useClient(injected);

  const [form, setForm] = useState<SettingsView | null>(null);
  const [saved, setSaved] = useState("");
  const [testMessage, setTestMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    client.settings
      .get()
      .then((value) => {
        if (!cancelled) setForm(value);
      })
      .catch((error: Error) => {
        if (!cancelled) setSaved(`读取配置失败：${error.message}`);
      });
    return () => {
      cancelled = true;
    };
  }, [client]);

  if (!form) {
    return (
      <div>
        <div className="screen-head">
          <h1>设置</h1>
        </div>
        <p className="muted">正在读取配置…</p>
      </div>
    );
  }

  const update = (patch: Partial<SettingsView>) => setForm({ ...form, ...patch });
  const updateBackground = (key: string, value: string) =>
    setForm({ ...form, background: { ...form.background, [key]: value } });

  // 后端：未配置返回空串，已配置返回 sk-***（Ruling F3）
  const needsKey = form.apiKey.trim() === "";

  const save = async () => {
    const patch: Partial<SettingsView> = { ...form };
    // 打码占位符绝不写回数据库
    if (patch.apiKey === MASK) delete patch.apiKey;
    try {
      const next = await client.settings.update(patch);
      setForm(next);
      setSaved("已保存到本机，重启后仍然有效");
    } catch (error) {
      setSaved(`保存失败：${(error as Error).message}`);
    }
  };

  const runTest = async () => {
    setTestMessage("连接中…");
    try {
      const result = await client.settings.test();
      setTestMessage(result.ok ? "连接正常，模型可用" : "还没有配置可用的 key");
    } catch (error) {
      setTestMessage(`连接失败：${(error as Error).message}`);
    }
  };

  return (
    <div>
      <div className="screen-head">
        <h1>设置</h1>
        <p>配置存在本机，重启后不需要再填。模型接口兼容 OpenAI 协议，可以换成任意兼容服务。</p>
      </div>

      {needsKey ? (
        <p className="notice">还需要填写 API Key，否则无法生成文章。</p>
      ) : null}

      <section className="block">
        <h2>模型</h2>
        <p className="hint">用于摘要、深读与复现方案；同一把 key 也用于 Search 与 Fetch。</p>
        <div className="row2">
          <TextField label="接口地址" value={form.baseUrl} onChange={(v) => update({ baseUrl: v })} />
          <TextField label="模型名" value={form.model} onChange={(v) => update({ model: v })} />
        </div>
        <SecretField
          label="API Key"
          value={form.apiKey}
          placeholder="sk-..."
          onChange={(v) => update({ apiKey: v })}
        />
        <div className="actions">
          <button type="button" className="btn" onClick={runTest}>
            测试连接
          </button>
          <span className="muted">{testMessage}</span>
        </div>
      </section>

      <section className="block">
        <h2>篇幅与窗口</h2>
        <div className="row2">
          <label className="field" htmlFor="window-days">
            <span className="field-label">抓取窗口</span>
            <select
              id="window-days"
              value={form.windowDays}
              onChange={(e) => update({ windowDays: Number(e.target.value) })}
            >
              <option value={7}>最近 7 天</option>
              <option value={14}>最近 14 天</option>
            </select>
          </label>
          <TextField
            label="分享时长（分钟）"
            value={String(form.shareMinutes)}
            onChange={(v) => update({ shareMinutes: Number(v) || 0 })}
          />
        </div>
        <p className="muted">
          一期目标字数 ≈ {form.shareMinutes} × {form.wordsPerMinute} ={" "}
          {form.shareMinutes * form.wordsPerMinute} 字
        </p>
      </section>

      <section className="block">
        <h2>你的研究背景</h2>
        <p className="hint">深读会引用这里的字段来解释「这篇对你有什么用」。留空的字段不会被引用。</p>
        {BACKGROUND_FIELDS.map(([key, label, hint]) => (
          <TextAreaField
            key={key}
            label={label}
            hint={hint}
            value={String(form.background?.[key] ?? "")}
            onChange={(v) => updateBackground(key, v)}
          />
        ))}
      </section>

      <div className="actions">
        <button type="button" className="btn primary" onClick={save}>
          保存
        </button>
        <span className="muted">{saved}</span>
      </div>
    </div>
  );
}
