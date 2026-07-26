import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api, setCsrfToken } from "../src/api/client";

afterEach(() => {
  vi.restoreAllMocks();
  setCsrfToken("");
});

describe("API client", () => {
  it("adds CSRF to mutations and preserves problem details", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    setCsrfToken("synthetic-token");
    await api("/projects", { method: "POST", json: { name: "Lab" } });
    const headers = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(headers.get("X-CSRF-Token")).toBe("synthetic-token");
    expect(fetchMock.mock.calls[0][1]?.credentials).toBe("include");

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({ title: "Forbidden", detail: "Object is outside this workspace.", status: 403 }),
        { status: 403, headers: { "Content-Type": "application/problem+json" } },
      ),
    );
    await expect(api("/projects/other")).rejects.toEqual(
      expect.objectContaining<ApiError>({ name: "ApiError" }),
    );
  });
});

