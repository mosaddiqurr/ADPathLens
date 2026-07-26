import { defineConfig, devices } from "@playwright/test";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"] },
      testIgnore: /mobile\.spec\.ts/,
    },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] }, testMatch: /mobile\.spec\.ts/ },
  ],
  webServer: [
    {
      command: "python scripts/e2e_server.py",
      cwd: "../backend",
      url: "http://127.0.0.1:8011/api/v1/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `${npmCommand} run dev -- --host 127.0.0.1 --port 5174 --strictPort`,
      cwd: ".",
      url: "http://127.0.0.1:5174",
      env: { VITE_API_PROXY_TARGET: "http://127.0.0.1:8011" },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
