import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

interface User {
  id: string;
  username: string;
  email: string;
  display_name: string | null;
  role: string;
  is_verified: boolean;
  created_at: string;
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string, displayName?: string) => Promise<void>;
  logout: () => void;
  getAuthHeaders: () => Record<string, string>;
  refreshAuth: () => Promise<boolean>;
}

const AuthContext = createContext<AuthContextType | null>(null);

const TOKEN_KEY = "truthtrace-token";
const REFRESH_KEY = "truthtrace-refresh";

function loadTokens(): { access: string | null; refresh: string | null } {
  try {
    return {
      access: localStorage.getItem(TOKEN_KEY),
      refresh: localStorage.getItem(REFRESH_KEY),
    };
  } catch {
    return { access: null, refresh: null };
  }
}

function saveTokens(access: string, refresh: string) {
  try {
    localStorage.setItem(TOKEN_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  } catch {}
}

function clearTokens() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
  } catch {}
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Restore session on mount
  useEffect(() => {
    const { access } = loadTokens();
    if (access) {
      // Verify token is still valid by fetching /api/auth/me
      fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${access}` },
      })
        .then((res) => {
          if (res.ok) return res.json();
          throw new Error("Token expired");
        })
        .then((user) => {
          const { refresh } = loadTokens();
          setState({
            user,
            accessToken: access,
            refreshToken: refresh,
            isAuthenticated: true,
            isLoading: false,
          });
        })
        .catch(() => {
          clearTokens();
          setState((s) => ({ ...s, isLoading: false }));
        });
    } else {
      setState((s) => ({ ...s, isLoading: false }));
    }
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "登录失败");
    }

    const data = await res.json();
    saveTokens(data.access_token, data.refresh_token);
    setState({
      user: data.user,
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      isAuthenticated: true,
      isLoading: false,
    });
  }, []);

  const register = useCallback(async (
    username: string,
    email: string,
    password: string,
    displayName?: string,
  ) => {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, email, password, display_name: displayName }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "注册失败");
    }

    const data = await res.json();
    saveTokens(data.access_token, data.refresh_token);
    setState({
      user: data.user,
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      isAuthenticated: true,
      isLoading: false,
    });
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setState({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
    });
  }, []);

  const refreshAuth = useCallback(async (): Promise<boolean> => {
    const { refresh } = loadTokens();
    if (!refresh) return false;

    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });

      if (!res.ok) {
        clearTokens();
        setState((s) => ({ ...s, isAuthenticated: false, user: null }));
        return false;
      }

      const data = await res.json();
      saveTokens(data.access_token, refresh);
      setState((s) => ({
        ...s,
        accessToken: data.access_token,
        refreshToken: refresh,
      }));
      return true;
    } catch {
      return false;
    }
  }, []);

  const getAuthHeaders = useCallback((): Record<string, string> => {
    if (state.accessToken) {
      return { Authorization: `Bearer ${state.accessToken}` };
    }
    return {};
  }, [state.accessToken]);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        login,
        register,
        logout,
        getAuthHeaders,
        refreshAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
