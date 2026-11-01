import type { ChangeEvent, ReactNode } from "react";

interface BaseProps {
  label: string;
  hint?: ReactNode;
  value: string;
  onChange: (value: string) => void;
  id?: string;
}

export function TextField({ label, hint, value, onChange, id }: BaseProps) {
  const inputId = id ?? `f-${label}`;
  return (
    <label className="field" htmlFor={inputId}>
      <span className="field-label">{label}</span>
      <input
        id={inputId}
        type="text"
        value={value}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

interface SecretProps extends Omit<BaseProps, "value" | "onChange"> {
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}

export function SecretField({ label, hint, value, onChange, id, placeholder }: SecretProps) {
  const inputId = id ?? `f-${label}`;
  return (
    <label className="field" htmlFor={inputId}>
      <span className="field-label">{label}</span>
      <input
        id={inputId}
        type="password"
        value={value}
        placeholder={placeholder}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

interface AreaProps extends BaseProps {}

export function TextAreaField({ label, hint, value, onChange, id }: AreaProps) {
  const inputId = id ?? `f-${label}`;
  return (
    <label className="field" htmlFor={inputId}>
      <span className="field-label">{label}</span>
      <textarea
        id={inputId}
        value={value}
        rows={3}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
      />
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}
