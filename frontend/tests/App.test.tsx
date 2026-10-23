import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";
import { AuthProvider } from "../src/features/auth/AuthContext";

afterEach(() => vi.restoreAllMocks());

describe("App", () => {
  it("shows login and the defensive authorized-use boundary", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/auth/me")) {
        return new Response(
          JSON.stringify({
            title: "Authentication required",
            detail: "Please sign in.",
            status: 401,
          }),
          {
            status: 401,
            headers: { "Content-Type": "application/problem+json" },
          },
        );
      }
      return new Response(JSON.stringify({ setup_required: false }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    render(
      <MemoryRouter initialEntries={["/login"]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>,
    );
    expect(
      await screen.findByRole("heading", { name: "ADPathLens" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Use only synthetic data/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });
});
