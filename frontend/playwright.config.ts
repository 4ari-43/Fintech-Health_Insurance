import { defineConfig } from "@playwright/test";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
const dataDir = mkdtempSync(join(tmpdir(), "policyiq-browser-tests-"));
const python =
  process.platform === "win32"
    ? resolve("../.venv/Scripts/python.exe")
    : resolve("../.venv/bin/python");
// Playwright supplies FORCE_COLOR; do not inherit the contradictory NO_COLOR flag.
delete process.env.NO_COLOR;
export default defineConfig({
  testDir: "./tests",
  timeout: 30000,
  workers: 2,
  fullyParallel: false,
  use: {
    baseURL: "http://127.0.0.1:5177",
    headless: true,
    trace: "retain-on-failure",
  },
  reporter: "list",
  webServer: [
    {
      command: `"${python}" -m uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8001 --no-access-log`,
      cwd: "..",
      url: "http://127.0.0.1:8001/api/health",
      env: {
        POLICYIQ_ORIGIN: "http://127.0.0.1:5176",
        POLICYIQ_DATA_DIR: dataDir,
        POLICYIQ_ENABLE_QUESTIONS: "false",
        POLICYIQ_ENV: "development",
      },
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 5176",
      url: "http://127.0.0.1:5176",
      env: { POLICYIQ_API_PROXY: "http://127.0.0.1:8001" },
      reuseExistingServer: false,
    },
    {
      command: "npm run dev:demo -- --port 5177",
      url: "http://127.0.0.1:5177",
      reuseExistingServer: false,
    },
  ],
});
