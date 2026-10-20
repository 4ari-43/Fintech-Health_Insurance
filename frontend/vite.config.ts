import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  if (command === "build" && (mode === "demo" || env.VITE_APP_MODE === "demo"))
    throw new Error(
      "Demo mode is development-only. Production must use the real API.",
    );
  return {
    plugins: [react(), tailwindcss()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": {
          target: process.env.POLICYIQ_API_PROXY || "http://127.0.0.1:8000",
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test-setup.ts"],
      exclude: ["tests/**", "node_modules/**"],
    },
  };
});
