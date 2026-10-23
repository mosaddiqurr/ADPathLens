/* Auth state and its hook intentionally share one module. */
/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { api, ApiError, errorMessage, setCsrfToken } from "../../api/client";
import type { User } from "../../types/api";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  localMode: boolean;
  error: string;
  signIn: (email: string, password: string) => Promise<void>;
  setup: (
    email: string,
    displayName: string,
    password: string,
  ) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [localMode, setLocalMode] = useState(false);
  const [error, setError] = useState("");
  const connection = useRef<Promise<{
    user: User | null;
    csrf_token: string;
    local: boolean;
  }> | null>(null);

  useEffect(() => {
    let alive = true;
    async function connect() {
      const status = await api<{ available: boolean }>("/auth/local-status");
      try {
        const currentUser = await api<User>("/auth/me");
        const token = await api<{ csrf_token: string }>("/auth/csrf");
        return {
          user: currentUser,
          csrf_token: token.csrf_token,
          local: status.available,
        };
      } catch (e) {
        if (!(e instanceof ApiError) || e.problem.status !== 401) throw e;
        if (!status.available)
          return { user: null, csrf_token: "", local: false };
        const session = await api<{ user: User; csrf_token: string }>(
          "/auth/local-session",
          {
            method: "POST",
            headers: { "X-ADPathLens-Local": "1" },
          },
        );
        return { ...session, local: true };
      }
    }
    // StrictMode replays effects. Share initialization so local setup is atomic from this tab.
    connection.current ??= connect();
    connection.current
      .then((session) => {
        if (!alive) return;
        setCsrfToken(session.csrf_token);
        setUser(session.user);
        setLocalMode(session.local);
      })
      .catch((e) => {
        if (alive) setError(errorMessage(e));
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      localMode,
      error,
      async signIn(email, password) {
        const response = await api<{ user: User; csrf_token: string }>(
          "/auth/login",
          {
            method: "POST",
            json: { email, password },
          },
        );
        setCsrfToken(response.csrf_token);
        setUser(response.user);
      },
      async setup(email, displayName, password) {
        const response = await api<{ user: User; csrf_token: string }>(
          "/auth/setup",
          {
            method: "POST",
            json: {
              email,
              display_name: displayName,
              password,
              authorization_confirmed: true,
            },
          },
        );
        setCsrfToken(response.csrf_token);
        setUser(response.user);
      },
      async signOut() {
        await api<void>("/auth/logout", { method: "POST" });
        setCsrfToken("");
        setUser(null);
      },
    }),
    [loading, user, localMode, error],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
