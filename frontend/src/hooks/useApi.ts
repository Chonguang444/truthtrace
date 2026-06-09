import { useState, useCallback, useRef, useMemo } from "react";
import { useAuth } from "../contexts/AuthContext";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const DEFAULT_TIMEOUT = 30000;
const MAX_RETRIES = 2;

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
  const { getAuthHeaders, refreshAuth } = useAuth();

  const request = useCallback(
    async (
      path: string,
      options?: RequestInit & { timeout?: number; retries?: number; auth?: boolean }
    ): Promise<T | null> => {
      if (abortRef.current) {
        abortRef.current.abort();
      }

      const controller = new AbortController();
      abortRef.current = controller;
      const timeout = options?.timeout ?? DEFAULT_TIMEOUT;
      const maxRetries = options?.retries ?? MAX_RETRIES;
      const needsAuth = options?.auth ?? false;
      const { retries: _, timeout: _t, auth: _a, ...fetchOptions } = options ?? {};

      let lastError: string | null = null;

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        if (attempt > 0) {
          await new Promise((r) => setTimeout(r, Math.pow(2, attempt - 1) * 1000));
        }

        try {
          setState((s) => ({ ...s, loading: true, error: null, retryCount: attempt }));

          const timeoutId = setTimeout(() => controller.abort(), timeout);

          // Build headers with auth if needed
          const headers: Record<string, string> = {
            "Content-Type": "application/json",
          };
          if (needsAuth) {
            const authHeaders = getAuthHeaders();
            Object.assign(headers, authHeaders);
          }

          const res = await fetch(`${API_BASE}${path}`, {
            headers,
            signal: controller.signal,
            ...fetchOptions,
          });

          clearTimeout(timeoutId);

          // 401: try refresh token once
          if (res.status === 401 && needsAuth && attempt === 0) {
            const refreshed = await refreshAuth();
            if (refreshed) continue;
          }

          if (!res.ok) {
            const errData = await res.json().catch(() => ({}));
            const msg = (errData as any).detail || `HTTP ${res.status}`;
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
          clearTimeout(timeout);
          if (err.name === "AbortError") {
            lastError = "请求超时或已取消";
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
    const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    const a = document.createElement("a");
    a.href = `${API_BASE}${url}`;
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
