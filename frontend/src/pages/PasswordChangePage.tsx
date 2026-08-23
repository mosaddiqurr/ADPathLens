import { useState, type FormEvent } from "react";
import { KeyRound } from "lucide-react";

import { api, jsonBody, setCsrfToken } from "../api/client";
import { Button, ErrorNotice, Field } from "../components/Ui";
import type { User } from "../types";

function stringValue(values: FormData, name: string): string {
  const value = values.get(name);
  return typeof value === "string" ? value : "";
}

export function PasswordChangePage({
  onChanged,
  onLogout,
}: {
  onChanged: (user: User) => void;
  onLogout: () => Promise<void>;
}) {
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(undefined);
    const values = new FormData(event.currentTarget);
    const currentPassword = stringValue(values, "current_password");
    const newPassword = stringValue(values, "new_password");
    const confirmation = stringValue(values, "confirmation");
    if (newPassword !== confirmation) {
      setError(new Error("New password and confirmation must match."));
      return;
    }
    setBusy(true);
    try {
      const result = await api<{ user: User; csrf_token: string }>("/auth/change-password", {
        method: "POST",
        ...jsonBody({ current_password: currentPassword, new_password: newPassword }),
      });
      setCsrfToken(result.csrf_token);
      onChanged(result.user);
    } catch (caught) {
      setError(caught);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell" id="main-content">
      <section className="auth-card" aria-labelledby="password-change-title">
        <div className="brand-mark">
          <KeyRound aria-hidden="true" />
        </div>
        <p className="eyebrow">Required security step</p>
        <h1 id="password-change-title">Replace your temporary password</h1>
        <p>
          Before continuing, choose a private password containing 12–128 characters. Other signed-in
          sessions will be invalidated after the change succeeds.
        </p>
        <ErrorNotice error={error} />
        <form onSubmit={(event) => void submit(event)}>
          <Field label="Temporary password">
            <input
              name="current_password"
              type="password"
              required
              autoComplete="current-password"
            />
          </Field>
          <Field label="New password" hint="Use 12–128 Unicode characters.">
            <input
              name="new_password"
              type="password"
              required
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
            />
          </Field>
          <Field label="Confirm new password">
            <input
              name="confirmation"
              type="password"
              required
              minLength={12}
              maxLength={128}
              autoComplete="new-password"
            />
          </Field>
          <Button type="submit" disabled={busy}>
            {busy ? "Changing password..." : "Change password and continue"}
          </Button>
        </form>
        <Button type="button" variant="secondary" onClick={() => void onLogout()} disabled={busy}>
          Sign out instead
        </Button>
      </section>
    </main>
  );
}
