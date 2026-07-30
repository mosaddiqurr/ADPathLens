import { useEffect, useState, type FormEvent } from "react";
import { ShieldCheck } from "lucide-react";

import { api, jsonBody, refreshCsrf, setCsrfToken } from "../api/client";
import { Button, ErrorNotice, Field } from "../components/Ui";
import type { User } from "../types";

const ACKNOWLEDGEMENT =
  "I confirm that I own this target or have explicit authorization to test it.";

export function AuthPage({
  setupRequired,
  onAuthenticated,
}: {
  setupRequired: boolean;
  onAuthenticated: (user: User) => void;
}) {
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void refreshCsrf().catch(setError);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(undefined);
    const values = new FormData(event.currentTarget);
    try {
      if (setupRequired) {
        const result = await api<{ user: User; csrf_token: string }>("/auth/setup", {
          method: "POST",
          ...jsonBody({
            setup_token: values.get("setup_token"),
            email: values.get("email"),
            display_name: values.get("display_name"),
            password: values.get("password"),
            authorization_acknowledgement: ACKNOWLEDGEMENT,
          }),
        });
        setCsrfToken(result.csrf_token);
        onAuthenticated(result.user);
      } else {
        const result = await api<{ user: User; csrf_token: string }>("/auth/login", {
          method: "POST",
          ...jsonBody({
            email: values.get("email"),
            password: values.get("password"),
          }),
        });
        setCsrfToken(result.csrf_token);
        onAuthenticated(result.user);
      }
    } catch (caught) {
      setError(caught);
      await refreshCsrf().catch(() => undefined);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell" id="main-content">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="brand-mark">
          <ShieldCheck aria-hidden="true" />
        </div>
        <p className="eyebrow">Authorized security testing only</p>
        <h1 id="auth-title">{setupRequired ? "Create the first administrator" : "Sign in"}</h1>
        <p>
          AuthZDiff compares approved requests across controlled profiles. Results require
          qualified human review.
        </p>
        <ErrorNotice error={error} />
        <form onSubmit={(event) => { void submit(event); }}>
          {setupRequired && (
            <>
              <Field label="Environment setup token">
                <input name="setup_token" type="password" required minLength={16} autoComplete="off" />
              </Field>
              <Field label="Display name">
                <input name="display_name" required autoComplete="name" />
              </Field>
            </>
          )}
          <Field label="Email address">
            <input name="email" type="email" required autoComplete="username" />
          </Field>
          <Field label="Password" hint={setupRequired ? "Use 12-128 Unicode characters." : undefined}>
            <input
              name="password"
              type="password"
              required
              minLength={setupRequired ? 12 : 1}
              autoComplete={setupRequired ? "new-password" : "current-password"}
            />
          </Field>
          {setupRequired && (
            <label className="checkbox">
              <input name="acknowledge" type="checkbox" required />
              <span>{ACKNOWLEDGEMENT}</span>
            </label>
          )}
          <Button type="submit" disabled={busy}>
            {busy ? "Please wait..." : setupRequired ? "Create administrator" : "Sign in"}
          </Button>
        </form>
      </section>
    </main>
  );
}
