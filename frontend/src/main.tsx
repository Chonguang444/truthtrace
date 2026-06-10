import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ErrorBoundary } from "./components/ErrorBoundary";
import "./index.css";
import "./i18n/config";

// --- Register Service Worker (PWA) ---
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker
      .register("/sw.js", { scope: "/" })
      .then((registration) => {
        console.log(
          `[PWA] Service Worker registered (scope: ${registration.scope})`
        );

        // Check for updates
        registration.addEventListener("updatefound", () => {
          const installingWorker = registration.installing;
          if (!installingWorker) return;

          installingWorker.addEventListener("statechange", () => {
            if (
              installingWorker.state === "installed" &&
              navigator.serviceWorker.controller
            ) {
              // New content available — notify user
              console.log("[PWA] New version available. Refresh to update.");
              // Could show a toast/snackbar here
            }
          });
        });
      })
      .catch((err) => {
        console.warn("[PWA] Service Worker registration failed:", err.message);
      });
  });
}

// --- Unregister SW in development (optional, uncomment to force-refresh) ---
// if (import.meta.env.DEV) {
//   navigator.serviceWorker?.getRegistrations().then((regs) => regs.forEach((r) => r.unregister()));
// }

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>
);
