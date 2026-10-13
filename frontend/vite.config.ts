import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxy = { "/api": process.env.VITE_API_PROXY_TARGET ?? "http://127.0.0.1:8020" };
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 4174, strictPort: true, proxy },
  preview: { host: "127.0.0.1", port: 4174, strictPort: true, proxy },
});
