import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  apiFetch,
  getAuthToken,
  setAuthToken,
  setUnauthorizedHandler,
} from "@/lib/api";

export interface AuthUser {
  id: string;
  email: string | null;
  is_admin: boolean;
}

interface AuthResponse {
  token: string;
  user: AuthUser;
}

interface AuthContextValue {
  user: AuthUser | null;
  /** True while the initial token check is in flight. */
  loading: boolean;
  isAuthenticated: boolean;
  /** Set when the server rejected a request with 401 (enforced-auth mode). */
  requiresLogin: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState<boolean>(!!getAuthToken());
  const [requiresLogin, setRequiresLogin] = useState(false);

  const logout = useCallback(() => {
    setAuthToken(null);
    setUser(null);
    qc.clear();
  }, [qc]);

  // Redirect/log out when any request reports 401.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setAuthToken(null);
      setUser(null);
      setRequiresLogin(true);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  // Bootstrap from a stored token on first load.
  useEffect(() => {
    let cancelled = false;
    if (!getAuthToken()) {
      setLoading(false);
      return;
    }
    apiFetch<AuthUser>("/api/auth/me")
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch(() => {
        if (!cancelled) {
          setAuthToken(null);
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await apiFetch<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAuthToken(res.token);
    setUser(res.user);
    setRequiresLogin(false);
    qc.clear();
  }, [qc]);

  const register = useCallback(async (email: string, password: string) => {
    const res = await apiFetch<AuthResponse>("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAuthToken(res.token);
    setUser(res.user);
    setRequiresLogin(false);
    qc.clear();
  }, [qc]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      isAuthenticated: !!user,
      requiresLogin,
      login,
      register,
      logout,
    }),
    [user, loading, requiresLogin, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
