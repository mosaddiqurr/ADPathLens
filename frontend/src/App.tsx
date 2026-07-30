import { useEffect, useState } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { api, refreshCsrf, setCsrfToken } from "./api/client";
import { ErrorNotice } from "./components/Ui";
import { AppLayout } from "./layouts/AppLayout";
import { AuditPage } from "./pages/AuditPage";
import { AuthPage } from "./pages/AuthPage";
import { Dashboard } from "./pages/Dashboard";
import { ProjectPage } from "./pages/ProjectPage";
import type { User } from "./types";

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [setupRequired, setSetupRequired] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>();

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      try {
        const setup = await api<{ setup_required: boolean }>("/auth/setup-status");
        if (!active) return;
        setSetupRequired(setup.setup_required);
        if (!setup.setup_required) {
          try {
            const current = await api<User>("/auth/me");
            setUser(current);
            await refreshCsrf();
          } catch {
            setUser(null);
          }
        }
      } catch (caught) {
        if (active) setError(caught);
      } finally {
        if (active) setLoading(false);
      }
    }
    void bootstrap();
    return () => {
      active = false;
    };
  }, []);

  async function logout() {
    try {
      await api<unknown>("/auth/logout", { method: "POST" });
    } finally {
      setCsrfToken(null);
      setUser(null);
    }
  }

  if (loading) {
    return <main className="loading-screen" aria-busy="true">Loading AuthZDiff...</main>;
  }
  if (error) {
    return <main className="loading-screen"><ErrorNotice error={error} /></main>;
  }
  if (!user) {
    return (
      <>
        <a className="skip-link" href="#main-content">Skip to main content</a>
        <AuthPage
          setupRequired={setupRequired}
          onAuthenticated={(authenticated) => {
            setUser(authenticated);
            setSetupRequired(false);
          }}
        />
      </>
    );
  }
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout user={user} onLogout={logout} />}>
          <Route index element={<Dashboard />} />
          <Route path="/projects/:projectId/:section" element={<ProjectPage />} />
          <Route
            path="/audit"
            element={user.role === "administrator" ? <AuditPage /> : <Navigate to="/" replace />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
