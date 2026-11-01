import type { ChangeEvent, ReactNode } from "react";

interface BaseProps {
  label: string;
  hint?: ReactNode;
  value: string;
  onChange: (value: string) => void;
  id?: string;
}

const inputId = (label: string, id?: string) => id ?? `f-${label}`;

export function TextField({ label, hint, value, onChange, id }: BaseProps) {
  const fieldId = inputId(label, id);
  return (
    <div className="field">
      <label className="field-label" htmlFor={fieldId}>
        {label}
      </label>
      <input
        id={fieldId}
        type="text"
        value={value}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
      {hint ? <span className="field-hint">{hint}</span> : null}
    </div>
  );
}

interface SecretProps extends Omit<BaseProps, "value" | "onChange"> {
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}

export function SecretField({ label, hint, value, onChange, id, placeholder }: SecretProps) {
  const fieldId = inputId(label, id);
  return (
    <div className="field">
      <label className="field-label" htmlFor={fieldId}>
        {label}
      </label>
      <input
        id={fieldId}
        type="password"
        value={value}
        placeholder={placeholder}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
      {hint ? <span className="field-hint">{hint}</span> : null}
    </div>
  );
}

export function TextAreaField({ label, hint, value, onChange, id }: BaseProps) {
  const fieldId = inputId(label, id);
  return (
    <div className="field">
      <label className="field-label" htmlFor={fieldId}>
        {label}
      </label>
      <textarea
        id={fieldId}
        value={value}
        rows={3}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
      />
      {hint ? <span className="field-hint">{hint}</span> : null}
    </div>
  );
}
