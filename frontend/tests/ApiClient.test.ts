import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup } from "@testing-library/react";

import { api, setCsrfToken } from "../src/api/client";

afterEach(() => {
  cleanup();
  setCsrfToken(null);
  vi.unstubAllGlobals();
});

describe("API client security", () => {
  it("uses cookies and a memory-only CSRF header for mutations", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    setCsrfToken("csrf-memory-value");

    await api("/projects", { method: "POST", body: JSON.stringify({ name: "Demo" }) });

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(init?.credentials).toBe("include");
    expect(headers.get("X-CSRF-Token")).toBe("csrf-memory-value");
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
