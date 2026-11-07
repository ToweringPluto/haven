import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // Forward API calls to the FastAPI dev server (uv run --directory backend poe serve),
    // so the browser sees one origin and no CORS setup is needed locally.
    proxy: {
      "/v1": "http://localhost:8000",
    },
  },
});
