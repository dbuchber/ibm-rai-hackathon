import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  server: { host: "127.0.0.1", port: 5180, strictPort: true, proxy: { "/api": process.env.API_TARGET ?? "http://127.0.0.1:17080" } },
});
