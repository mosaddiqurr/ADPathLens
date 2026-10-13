import { defineConfig, devices } from "@playwright/test";
const backendPort = String(Number(process.env.E2E_BACKEND_PORT ?? 8020));
const frontendPort = String(Number(process.env.E2E_FRONTEND_PORT ?? 4174));
const baseURL = `http://127.0.0.1:${frontendPort}`;
const previewDirectory = process.env.E2E_PREVIEW_DIR ?? "dist";
export default defineConfig({
  testDir: "./e2e", testMatch: /final\.spec\.ts/, outputDir: "./test-results",
  fullyParallel: false, workers: 1, timeout: 60_000, expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: { baseURL, trace: "retain-on-failure", screenshot: "only-on-failure" },
  webServer: [
    { command: `"${process.platform === "win32" ? "../.venv/Scripts/python.exe" : "../.venv/bin/python"}" -m uvicorn app.main:app --host 127.0.0.1 --port ${backendPort} --no-access-log --limit-concurrency 16`,
      cwd: "../backend", url: `http://127.0.0.1:${backendPort}/api/v1/ready`, reuseExistingServer: !process.env.CI, timeout: 30_000,
      env: { ALLOWED_HOSTS: "localhost,127.0.0.1", ALLOWED_FRONTEND_ORIGINS: `${baseURL},http://localhost:${frontendPort}` } },
    { command: `npm run preview -- --port ${frontendPort} --outDir "${previewDirectory}"`, url: baseURL, reuseExistingServer: !process.env.CI, timeout: 30_000 },
  ],
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 }, ...(process.env.CI ? {} : { channel: "msedge" as const }) } },
    { name: "mobile", use: { ...devices["Pixel 7"], ...(process.env.CI ? {} : { channel: "msedge" as const }) } },
  ],
});
