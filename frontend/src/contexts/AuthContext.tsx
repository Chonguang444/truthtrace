import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";  // Empty = relative URL → Vite proxy / Nginx

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

// In-memory token storage (not localStorage — prevents XSS token theft)
let inMemoryAccessToken: string | null = null;
let inMemoryRefreshToken: string | null = null;

function saveTokens(access: string, refresh: string) {
  inMemoryAccessToken = access;
  inMemoryRefreshToken = refresh;
}

function clearTokens() {
  inMemoryAccessToken = null;
  inMemoryRefreshToken = null;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    refreshToken: null,
    isAuthenticated: false,
    isLoading: true,
  });

  // Restore session on mount via httpOnly cookie (secure) or in-memory token
  useEffect(() => {
    // Try cookie-based session restore first (httpOnly, not XSS-accessible)
    fetch(`${API_BASE}/api/auth/me`, {
      credentials: "include",
    })
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error("Not authenticated");
      })
      .then((data) => {
        // data.user: user profile, data.access_token: fresh token for Bearer auth
        if (data.access_token) {
          // Store the fresh token in memory for subsequent Bearer auth
          inMemoryAccessToken = data.access_token;
        }
        setState({
          user: data.user,
          accessToken: data.access_token || null,
          refreshToken: inMemoryRefreshToken,
          isAuthenticated: true,
          isLoading: false,
        });
      })
      .catch(() => {
        // Cookie auth failed — user needs to log in
        clearTokens();
        setState((s) => ({ ...s, isLoading: false }));
      });
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
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
      credentials: "include",
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
    // Call logout endpoint to clear httpOnly cookies
    fetch(`${API_BASE}/api/auth/logout`, {
      method: "POST",
      credentials: "include",
    }).catch(() => {});
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
    const refresh = inMemoryRefreshToken;
    if (!refresh) {
      // Try cookie-based refresh as fallback
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          credentials: "include",
        });
        if (!res.ok) {
          clearTokens();
          setState((s) => ({ ...s, isAuthenticated: false, user: null }));
          return false;
        }
        const data = await res.json();
        if (data.access_token) {
          inMemoryAccessToken = data.access_token;
        }
        setState((s) => ({ ...s, accessToken: data.access_token || null, user: data.user, isAuthenticated: true }));
        return true;
      } catch {
        return false;
      }
    }

    try {
      const res = await fetch(`${API_BASE}/api/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ refresh_token: refresh }),
      });

      if (!res.ok) {
        clearTokens();
        setState((s) => ({ ...s, isAuthenticated: false, user: null }));
        return false;
      }

      const data = await res.json();
      inMemoryAccessToken = data.access_token;
      setState((s) => ({
        ...s,
        accessToken: data.access_token,
      }));
      return true;
    } catch {
      return false;
    }
  }, []);

  const getAuthHeaders = useCallback((): Record<string, string> => {
    const token = inMemoryAccessToken || state.accessToken;
    if (token) {
      return { Authorization: `Bearer ${token}` };
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
