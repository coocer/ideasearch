const LABELS = ["", "了解", "关注", "深入"] as const;

export default function Gauge({ level }: { level: 1 | 2 | 3 }) {
  const safe = Math.min(3, Math.max(1, Math.round(Number(level) || 1))) as 1 | 2 | 3;
  const label = LABELS[safe] ?? "";
  return (
    <span className="gauge-wrap">
      <span className="gauge" role="img" aria-label={`阅读深度：${label}`}>
        {[1, 2, 3].map((step) => (
          <i key={step} className={step <= safe ? `on${step === 3 ? " top" : ""}` : ""} />
        ))}
      </span>
      <span className="gauge-label">{label}</span>
    </span>
  );
}
