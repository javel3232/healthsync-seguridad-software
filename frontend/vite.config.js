import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // Solo para "npm run dev": redirige /api a la aplicación levantada con Docker.
  server: {
    proxy: { "/api": "http://127.0.0.1:8080" },
  },
});
