import type { PropsWithChildren, ReactNode } from "react";

export function Button({
  children,
  variant = "primary",
  ...props
}: PropsWithChildren<
  React.ButtonHTMLAttributes<HTMLButtonElement> & {
    variant?: "primary" | "secondary" | "danger";
  }
>) {
  return (
    <button className={`button button-${variant}`} {...props}>
      {children}
    </button>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string | undefined;
  children: ReactNode;
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  );
}

export function Empty({ children }: PropsWithChildren) {
  return <p className="empty">{children}</p>;
}

export function ErrorNotice({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="notice notice-error" role="alert">
      {error instanceof Error ? error.message : "The request could not be completed."}
    </div>
  );
}

export function Status({ value }: { value: string }) {
  return <span className={`status status-${value.replaceAll("_", "-")}`}>{value}</span>;
}

export function Panel({
  title,
  description,
  action,
  children,
}: PropsWithChildren<{ title: string; description?: string; action?: ReactNode }>) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}
