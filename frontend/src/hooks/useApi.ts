import { useState, useCallback, useRef, useMemo } from "react";
import { useAuth } from "../contexts/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";  // Empty = relative URL → Vite proxy / Nginx
const DEFAULT_TIMEOUT = 30000;
const MAX_RETRIES = 2;
const CSRF_CACHE_DURATION = 45 * 60 * 1000;  // 45 min (CSRF token lives 1 hour)
let _csrfToken: string | null = null;
let _csrfFetchedAt: number = 0;

/**
 * 获取 CSRF 令牌 (带缓存避免每次请求都获取)
 * 用于所有状态变更请求 (POST/PUT/PATCH/DELETE)
 */
async function getCsrfToken(): Promise<string> {
  const now = Date.now();
  if (_csrfToken && (now - _csrfFetchedAt) < CSRF_CACHE_DURATION) {
    return _csrfToken;
  }
  try {
    const res = await fetch(`${API_BASE}/api/auth/csrf-token`, {
      credentials: "include",
      signal: AbortSignal.timeout(5000),
    });
    if (res.ok) {
      const data = await res.json();
      _csrfToken = data.csrf_token || "";
      _csrfFetchedAt = now;
      return _csrfToken || "";
    }
  } catch { /* 非阻塞: CSRF 不可用时回退到无头模式 */ }
  return "";
}

/**
 * 输入净化 — 防止 XSS 从用户输入渗入
 * 移除危险标签和事件处理器
 */
export function sanitizeInput(input: string): string {
  if (!input) return "";
  return input
    .replace(/<script[^>]*>.*?<\/script>/gi, "")
    .replace(/<iframe[^>]*>.*?<\/iframe>/gi, "")
    .replace(/<object[^>]*>.*?<\/object>/gi, "")
    .replace(/<embed[^>]*>/gi, "")
    .replace(/javascript\s*:/gi, "")
    .replace(/on\w+\s*=\s*["'][^"']*["']/gi, "")
    .replace(/on\w+\s*=\s*\S+/gi, "")
    .trim();
}

/**
 * 文本显示净化 — 转义 HTML 实体
 * (用于用户生成内容的纯文本展示)
 */
export function escapeHtml(text: string): string {
  const map: Record<string, string> = {
    "&": "&amp;", "<": "&lt;", ">": "&gt;",
    '"': "&quot;", "'": "&#039;",
  };
  return text.replace(/[&<>"']/g, (ch) => map[ch] || ch);
}

interface ApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  retryCount: number;
}

export function useApi<T>() {
  const [state, setState] = useState<ApiState<T>>({
    data: null,
    loading: false,
    error: null,
    retryCount: 0,
  });
  const abortRef = useRef<AbortController | null>(null);
  const lastPathRef = useRef<string>("");
  const { getAuthHeaders, refreshAuth } = useAuth();

  const request = useCallback(
    async (
      path: string,
      options?: RequestInit & { timeout?: number; retries?: number; auth?: boolean }
    ): Promise<T | null> => {
      // Only abort if the path changed (avoid race between unrelated requests)
      if (abortRef.current && lastPathRef.current !== path) {
        abortRef.current.abort();
      }
      lastPathRef.current = path;

      const controller = new AbortController();
      abortRef.current = controller;
      const timeoutMs = options?.timeout ?? DEFAULT_TIMEOUT;
      const maxRetries = options?.retries ?? MAX_RETRIES;
      const needsAuth = options?.auth ?? false;
      const { retries: _, timeout: _t, auth: _a, ...fetchOptions } = options ?? {};

      let lastError: string | null = null;

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        if (attempt > 0) {
          await new Promise((r) => setTimeout(r, Math.pow(2, attempt - 1) * 1000));
        }

        let timeoutId: ReturnType<typeof setTimeout> | null = null;
        try {
          setState((s) => ({ ...s, loading: true, error: null, retryCount: attempt }));

          timeoutId = setTimeout(() => controller.abort(), timeoutMs);

          // Build headers with auth if needed
          const headers: Record<string, string> = {
            "Content-Type": "application/json",
          };
          if (needsAuth) {
            const authHeaders = getAuthHeaders();
            Object.assign(headers, authHeaders);
          }
          // Inject CSRF token for state-changing requests
          const isMutation = options?.method && ["POST", "PUT", "PATCH", "DELETE"].includes(options.method.toUpperCase());
          if (isMutation) {
            const csrfToken = await getCsrfToken();
            if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
          }

          const res = await fetch(`${API_BASE}${path}`, {
            headers,
            signal: controller.signal,
            credentials: "include",  // Always include cookies for httpOnly auth
            ...fetchOptions,
          });

          clearTimeout(timeoutId);

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            const msg = (errData as any).detail || `HTTP ${res.status}`;
            if (res.status === 401 && attempt === 0) {
              // Try cookie-based refresh first, then in-memory
              const refreshed = await refreshAuth();
              if (refreshed) continue;
            }
            if (res.status >= 500 && attempt < maxRetries) {
              lastError = msg;
              continue;
            }
            throw new Error(msg);
          }

          const data = await res.json();
          setState({ data, loading: false, error: null, retryCount: attempt });
          return data;

        } catch (err: any) {
          if (timeoutId) clearTimeout(timeoutId);
          if (err.name === "AbortError") {
            // Only report timeout if it was THIS request that timed out (not aborted by new request)
            if (lastPathRef.current === path) {
              lastError = "请求超时或已取消";
            }
            break;
          }
          lastError = err.message || "请求失败";
          if (attempt >= maxRetries) break;
        }
      }

      setState((s) => ({ ...s, loading: false, error: lastError }));
      return null;
    },
    [getAuthHeaders, refreshAuth]
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { ...state, request, cancel };
}

// Convenience hooks
export function useSearch() {
  const api = useApi<any>();
  const search = (q: string, filters?: Record<string, string>) => {
    const params = new URLSearchParams({ q, ...filters });
    return api.request(`/api/search?${params}`);
  };
  return { ...api, search };
}

export function useEvent(eventId: string | undefined) {
  const api = useApi<any>();
  const fetch = () => {
    if (!eventId) return Promise.resolve(null);
    return api.request(`/api/events/${eventId}`);
  };
  return { ...api, fetch };
}

export function useTrace() {
  const api = useApi<any>();
  const submit = (url: string, deepTrace = false) =>
    api.request("/api/trace", {
      method: "POST",
      body: JSON.stringify({ url, deep_trace: deepTrace }),
    });
  return { ...api, submit };
}

export function useTaskStatus(taskId: string | null) {
  const api = useApi<any>();
  const poll = () => {
    if (!taskId) return Promise.resolve(null);
    return api.request(`/api/tasks/${taskId}`, { timeout: 5000 });
  };
  return { ...api, poll };
}

export function useRumors() {
  const api = useApi<any>();
  const fetch = (verdict?: string, limit = 20, offset = 0) => {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (verdict) params.set("verdict", verdict);
    return api.request(`/api/rumors?${params}`);
  };
  return { ...api, fetch };
}

// --- Auth-required convenience hooks ---

export function useFavorites() {
  const api = useApi<any>();

  const list = (limit = 20, offset = 0) =>
    api.request(`/api/auth/me/favorites?limit=${limit}&offset=${offset}`, { auth: true });

  const add = (eventId: string, note?: string) =>
    api.request("/api/auth/me/favorites", {
      method: "POST",
      body: JSON.stringify({ event_id: eventId, note }),
      auth: true,
    });

  const remove = (eventId: string) =>
    api.request(`/api/auth/me/favorites/${eventId}`, {
      method: "DELETE",
      auth: true,
    });

  return { ...api, list, add, remove };
}

export function useSubscriptions() {
  const api = useApi<any>();

  const list = () =>
    api.request("/api/auth/me/subscriptions", { auth: true });

  const create = (params: { event_id?: string; keyword?: string; notify_rumor?: boolean; notify_propagation?: boolean }) =>
    api.request("/api/auth/me/subscriptions", {
      method: "POST",
      body: JSON.stringify(params),
      auth: true,
    });

  const cancel = (subId: string) =>
    api.request(`/api/auth/me/subscriptions/${subId}`, {
      method: "DELETE",
      auth: true,
    });

  return { ...api, list, create, cancel };
}

export function useExport() {
  const download = useCallback((url: string, filename: string) => {
    const base = import.meta.env.VITE_API_BASE_URL || "";
    const a = document.createElement("a");
    a.href = `${base}${url}`;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }, []);

  return {
    exportEventsCSV: (params?: Record<string, string>) => {
      const qs = params ? "?" + new URLSearchParams(params).toString() : "";
      download(`/api/export/events/csv${qs}`, `truthtrace_events_${new Date().toISOString().slice(0, 10)}.csv`);
    },
    exportSourcesCSV: (eventId: string) =>
      download(`/api/export/events/${eventId}/sources/csv`, `truthtrace_sources_${eventId.slice(0, 8)}.csv`),
    exportReportPDF: (eventId: string) =>
      download(`/api/export/events/${eventId}/report/pdf`, `truthtrace_report_${eventId.slice(0, 8)}.pdf`),
  };
}
