import { afterEach, expect, test, vi } from "vitest";
import { apiUrl } from "../src/api/url";

afterEach(() => vi.unstubAllEnvs());

test("static hosting sends requests and protected downloads to the configured origin", () => {
  vi.stubEnv("VITE_API_URL", "https://api.adpathlens.example/");
  expect(apiUrl("/auth/me")).toBe(
    "https://api.adpathlens.example/api/v1/auth/me",
  );
  expect(apiUrl("/reports/123/download")).toBe(
    "https://api.adpathlens.example/api/v1/reports/123/download",
  );
});

test("local development keeps the Vite API proxy", () => {
  vi.stubEnv("VITE_API_URL", "");
  expect(apiUrl("/auth/me")).toBe("/api/v1/auth/me");
});
