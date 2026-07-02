import path from "node:path"
import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"

const rootDir = import.meta.dirname

// Assets are loaded from a file:// URL inside pywebview, so use relative paths.
export default defineConfig({
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(rootDir, "./src"),
    },
  },
  build: {
    outDir: path.resolve(
      rootDir,
      "../src/fin_ai_stats_extract/resources/webui",
    ),
    emptyOutDir: true,
  },
})
