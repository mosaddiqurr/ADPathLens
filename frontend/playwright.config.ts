import { defineConfig, devices } from "@playwright/test";
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const builtFrontend = process.env.ADPATHLENS_BUILT_E2E === "1";
const sharedSession = process.env.ADPATHLENS_SHARED_E2E === "1";
const frontendPort = Number(process.env.ADPATHLENS_E2E_FRONTEND_PORT ?? 5174);
const backendPort = Number(process.env.ADPATHLENS_E2E_BACKEND_PORT ?? 8011);
const virtualPython = resolve(
  "../backend/.venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
const pythonCommand =
  process.env.ADPATHLENS_PYTHON ??
  (existsSync(virtualPython) ? virtualPython : "python");

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  use: {
    baseURL:
      process.env.ADPATHLENS_E2E_BASE_URL ?? `http://127.0.0.1:${frontendPort}`,
    ignoreHTTPSErrors: process.env.ADPATHLENS_EXTERNAL_E2E === "1",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
      testIgnore: sharedSession
        ? /(?:mobile|journey|appearance)\.spec\.ts/
        : /(?:mobile|shared)\.spec\.ts/,
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
      testMatch: sharedSession ? /never-match/ : /mobile\.spec\.ts/,
    },
  ],
  webServer:
    process.env.ADPATHLENS_EXTERNAL_E2E === "1"
      ? []
      : [
          {
            command: `"${pythonCommand}" scripts/e2e_server.py`,
            cwd: "../backend",
            url: `http://127.0.0.1:${backendPort}/api/v1/health`,
            reuseExistingServer: false,
            timeout: 120_000,
          },
          {
            command: builtFrontend
              ? `${npmCommand} exec vite -- preview --host 127.0.0.1 --port ${frontendPort} --strictPort`
              : `${npmCommand} run dev -- --host 127.0.0.1 --port ${frontendPort} --strictPort`,
            cwd: ".",
            url: `http://127.0.0.1:${frontendPort}`,
            env: { VITE_API_PROXY_TARGET: `http://127.0.0.1:${backendPort}` },
            reuseExistingServer: false,
            timeout: 120_000,
          },
        ],
});
