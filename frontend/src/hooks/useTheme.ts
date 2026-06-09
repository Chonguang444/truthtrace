import { useState, useEffect, useCallback } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "truthtrace-theme";

function getSystemTheme(): "light" | "dark" {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function getStoredTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {}
  return "system";
}

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  const resolved = theme === "system" ? getSystemTheme() : theme;
  root.classList.toggle("dark", resolved === "dark");
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(getStoredTheme);

  // Apply on mount and when theme changes
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Listen for system theme changes (when in "system" mode)
  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      if (theme === "system") {
        applyTheme("system");
      }
    };
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme]);

  const setTheme = useCallback((newTheme: Theme) => {
    setThemeState(newTheme);
    try {
      localStorage.setItem(STORAGE_KEY, newTheme);
    } catch {}
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => {
      const cycle: Record<Theme, Theme> = { light: "dark", dark: "system", system: "light" };
      const next = cycle[prev];
      applyTheme(next);
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {}
      return next;
    });
  }, []);

  const isDark = theme === "dark" || (theme === "system" && getSystemTheme() === "dark");

  return { theme, setTheme, toggleTheme, isDark };
}
