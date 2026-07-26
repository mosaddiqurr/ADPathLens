import { Network, ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Redirect, useHistory } from "react-router-dom";

import { api, errorMessage } from "../api/client";
import { StatusMessage } from "../components/common/StatusMessage";
import { useAuth } from "../features/auth/AuthContext";

export function AuthPage() {
  const { user, signIn, setup } = useAuth();
  const history = useHistory();
  const [setupRequired, setSetupRequired] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    api<{ setup_required: boolean }>("/auth/setup-status")
      .then((status) => setSetupRequired(status.setup_required))
      .catch((reason) => setError(errorMessage(reason)));
  }, []);

  if (user) return <Redirect to="/" />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      if (setupRequired) {
        if (!authorizationConfirmed) {
          setError("Confirm the authorized-use requirement before creating the administrator.");
          return;
        }
        await setup(email, displayName, password);
      } else {
        await signIn(email, password);
      }
      history.push("/");
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main id="main-content" className="auth-shell">
      <section className="auth-intro">
        <div className="brand-icon large"><Network size={30} /></div>
        <p className="eyebrow">Defensive graph analysis</p>
        <h1>ADPathLens</h1>
        <p>
          Trace modeled privilege relationships, explain evidence, simulate defensive changes,
          and keep every decision under human review.
        </p>
        <div className="boundary-card">
          <ShieldCheck size={22} />
          <span>
            Use only synthetic data or information collected from systems you own or are
            explicitly authorized to assess.
          </span>
        </div>
      </section>
      <section className="auth-card" aria-labelledby="auth-title">
        <p className="eyebrow">{setupRequired ? "First run" : "Welcome back"}</p>
        <h2 id="auth-title">{setupRequired ? "Create administrator" : "Sign in"}</h2>
        <StatusMessage message={error} tone="danger" />
        <form onSubmit={(event) => void submit(event)} className="form-stack">
          {setupRequired && (
            <label>
              Display name
              <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} required />
            </label>
          )}
          <label>
            Email
            <input type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete={setupRequired ? "new-password" : "current-password"}
              minLength={setupRequired ? 12 : 1}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          {setupRequired && (
            <label className="check-row">
              <input
                type="checkbox"
                checked={authorizationConfirmed}
                onChange={(event) => setAuthorizationConfirmed(event.target.checked)}
              />
              I understand and accept the authorized-use requirement.
            </label>
          )}
          <button className="primary-button" disabled={submitting}>
            {submitting ? "Please wait…" : setupRequired ? "Create secure workspace" : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}
