import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  outputDir: "./test-results",
  fullyParallel: false,
  workers: 1,
  timeout: 120_000,
  expect: { timeout: 10_000 },
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: process.env.AUTHZDIFF_E2E_BASE_URL ?? "http://127.0.0.1:4174",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      testMatch: /release\.spec\.ts/,
      use: {
        ...devices["Desktop Chrome"],
        channel: "msedge",
      },
    },
    {
      name: "mobile",
      testMatch: /mobile\.spec\.ts/,
      dependencies: ["desktop"],
      use: {
        ...devices["Pixel 7"],
        channel: "msedge",
      },
    },
  ],
});
