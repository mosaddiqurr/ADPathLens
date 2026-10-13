import { afterEach, describe, expect, it, vi } from "vitest";
import { inspectInput, userMessage } from "../src/api/client";

afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
describe("safe stateless API client", () => {
  it("hides raw server errors", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Traceback: private database password" }), { status: 500 })));
    try { await inspectInput({ filename: "a.json", content: "[]" }); }
    catch (error) { expect(userMessage(error)).toBe("The request could not be completed."); }
  });
  it("rejects malformed successful responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("{}", { status: 200 })));
    await expect(inspectInput({ filename: "a.json", content: "[]" })).rejects.toThrow("The request could not be completed.");
  });
  it("uses no cookies or browser cache", async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ filename: "a.json", format: "snapshot", format_label: "JSON", record_count: 1, warnings: [] })));
    vi.stubGlobal("fetch", fetch);
    await inspectInput({ filename: "a.json", content: "[]" });
    expect(fetch).toHaveBeenCalledWith("/api/v1/inspect", expect.objectContaining({ credentials: "omit", cache: "no-store" }));
  });
  it("routes requests to the configured backend origin", async () => {
    vi.stubEnv("VITE_API_URL", "https://api.example.invalid/");
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ filename: "a.json", format: "snapshot", format_label: "JSON", record_count: 1, warnings: [] })));
    vi.stubGlobal("fetch", fetch);
    await inspectInput({ filename: "a.json", content: "[]" });
    expect(fetch).toHaveBeenCalledWith("https://api.example.invalid/api/v1/inspect", expect.objectContaining({ credentials: "omit" }));
  });
});
