import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        timeout: 30000,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          // Graph visualization libraries (heavy, lazy-loaded via page tabs)
          "vendor-graph": ["cytoscape", "d3"],
          // Internationalization
          "vendor-i18n": ["i18next", "react-i18next", "i18next-browser-languagedetector"],
          // React ecosystem
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          // UI primitives
          "vendor-ui": ["lucide-react", "@radix-ui/react-slot", "class-variance-authority", "clsx", "tailwind-merge"],
        },
      },
    },
    chunkSizeWarningLimit: 600,
    target: "es2020",
    minify: "esbuild",
  },
});
