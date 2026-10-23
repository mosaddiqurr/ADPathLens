import type { ReactNode } from "react";
import { Redirect, Route, Switch } from "react-router-dom";
import { useAuth } from "./features/auth/AuthContext";
import { ProductProvider } from "./features/product/ProductContext";
import { AppLayout } from "./layouts/AppLayout";
import { AuthPage } from "./pages/AuthPage";
import { HomePage, AboutPage } from "./pages/WelcomePages";
import { AnalyzePage } from "./pages/ProductPages";
import { ResultsPage } from "./pages/ResultsPage";

function AnalysisSession({ children }: { children: ReactNode }) {
  const { user, loading, error } = useAuth();
  if (loading)
    return (
      <div className="page">
        <p role="status" className="loading-state">
          Opening analysis session…
        </p>
      </div>
    );
  if (error)
    return (
      <div className="page">
        <section className="empty-environment">
          <h1>Could not open analysis</h1>
          <p role="alert">{error}</p>
          <button
            className="primary-button"
            onClick={() => window.location.reload()}
          >
            Try again
          </button>
        </section>
      </div>
    );
  if (!user) return <Redirect to="/login" />;
  return <>{children}</>;
}
export function App() {
  return (
    <Switch>
      <Route path="/login" component={AuthPage} />
      <Route>
        <ProductProvider>
          <AppLayout>
            <Switch>
              <Route path="/" exact component={HomePage} />
              <Route path="/analyze" exact>
                <AnalysisSession>
                  <AnalyzePage />
                </AnalysisSession>
              </Route>
              <Route path="/results" exact>
                <AnalysisSession>
                  <ResultsPage />
                </AnalysisSession>
              </Route>
              <Route path="/about" exact component={AboutPage} />
              <Route
                path={[
                  "/paths",
                  "/fixes",
                  "/reports",
                  "/findings",
                  "/snapshots",
                ]}
              >
                <Redirect to="/results" />
              </Route>
              <Route path={["/settings", "/admin"]}>
                <Redirect to="/about" />
              </Route>
              <Route path={["/projects", "/demo"]}>
                <Redirect to="/analyze" />
              </Route>
              <Route>
                <Redirect to="/" />
              </Route>
            </Switch>
          </AppLayout>
        </ProductProvider>
      </Route>
    </Switch>
  );
}
