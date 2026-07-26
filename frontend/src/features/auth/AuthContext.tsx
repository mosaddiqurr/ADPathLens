/* Auth state and its hook intentionally share one module. */
/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { api, setCsrfToken } from "../../api/client";
import type { User } from "../../types/api";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  setup: (email: string, displayName: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api<User>("/auth/me")
      .then(async (currentUser) => {
        const token = await api<{ csrf_token: string }>("/auth/csrf");
        setCsrfToken(token.csrf_token);
        setUser(currentUser);
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      async signIn(email, password) {
        const response = await api<{ user: User; csrf_token: string }>("/auth/login", {
          method: "POST",
          json: { email, password },
        });
        setCsrfToken(response.csrf_token);
        setUser(response.user);
      },
      async setup(email, displayName, password) {
        const response = await api<{ user: User; csrf_token: string }>("/auth/setup", {
          method: "POST",
          json: {
            email,
            display_name: displayName,
            password,
            authorization_confirmed: true,
          },
        });
        setCsrfToken(response.csrf_token);
        setUser(response.user);
      },
      async signOut() {
        await api<void>("/auth/logout", { method: "POST" });
        setCsrfToken("");
        setUser(null);
      },
    }),
    [loading, user],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
