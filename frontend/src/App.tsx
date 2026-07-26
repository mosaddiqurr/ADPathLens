import type { ReactNode } from "react";
import { Redirect, Route, Switch } from "react-router-dom";

import { useAuth } from "./features/auth/AuthContext";
import { AppLayout } from "./layouts/AppLayout";
import { AuditPage, SettingsPage } from "./pages/AdminPages";
import { AuthPage } from "./pages/AuthPage";
import { ComparisonPage } from "./pages/ComparisonPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DemoPage } from "./pages/DemoPage";
import { FindingDetailPage } from "./pages/FindingDetailPage";
import { FindingsPage } from "./pages/FindingsPage";
import { GraphPage } from "./pages/GraphPage";
import { ImportPage } from "./pages/ImportPage";
import { PathPage } from "./pages/PathPage";
import { ProjectPage } from "./pages/ProjectPage";
import { RemediationPage } from "./pages/RemediationPage";
import { ReportsPage } from "./pages/ReportsPage";

function ProtectedRoute({
  children,
  path,
  exact = false,
}: {
  children: ReactNode;
  path: string;
  exact?: boolean;
}) {
  const { user, loading } = useAuth();
  return (
    <Route
      path={path}
      exact={exact}
      render={() => {
        if (loading) return <main className="loading-screen">Loading secure workspace…</main>;
        if (!user) return <Redirect to="/login" />;
        return <AppLayout>{children}</AppLayout>;
      }}
    />
  );
}

function AdministratorOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return user?.role === "administrator" ? <>{children}</> : <Redirect to="/" />;
}

export function App() {
  return (
    <Switch>
      <Route path="/login" component={AuthPage} />
      <ProtectedRoute path="/" exact><DashboardPage /></ProtectedRoute>
      <ProtectedRoute path="/workspaces" exact><DashboardPage workspaceOnly /></ProtectedRoute>
      <ProtectedRoute path="/projects/:projectId" exact><ProjectPage /></ProtectedRoute>
      <ProtectedRoute path="/projects/:projectId/imports" exact><ImportPage /></ProtectedRoute>
      <ProtectedRoute path="/snapshots/:snapshotId/graph" exact><GraphPage /></ProtectedRoute>
      <ProtectedRoute path="/snapshots/:snapshotId/paths" exact><PathPage /></ProtectedRoute>
      <ProtectedRoute path="/projects/:projectId/findings" exact><FindingsPage /></ProtectedRoute>
      <ProtectedRoute path="/findings/:findingId" exact><FindingDetailPage /></ProtectedRoute>
      <ProtectedRoute path="/projects/:projectId/remediation" exact><RemediationPage /></ProtectedRoute>
      <ProtectedRoute path="/projects/:projectId/comparisons" exact><ComparisonPage /></ProtectedRoute>
      <ProtectedRoute path="/projects/:projectId/reports" exact><ReportsPage /></ProtectedRoute>
      <ProtectedRoute path="/demo" exact><DemoPage /></ProtectedRoute>
      <ProtectedRoute path="/admin/audit" exact><AdministratorOnly><AuditPage /></AdministratorOnly></ProtectedRoute>
      <ProtectedRoute path="/admin/settings" exact><AdministratorOnly><SettingsPage /></AdministratorOnly></ProtectedRoute>
      <Route><Redirect to="/" /></Route>
    </Switch>
  );
}
