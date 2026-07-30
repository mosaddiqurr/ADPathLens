import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";

function jsonResponse(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderApp() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <App />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App authentication boundary", () => {
  it("shows real first-administrator fields and authorization acknowledgement", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ setup_required: true }))
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "preauth-csrf" }));
    vi.stubGlobal("fetch", fetchMock);

    renderApp();

    expect(
      await screen.findByRole("heading", { name: "Create the first administrator" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Environment setup token")).toHaveAttribute("type", "password");
    expect(screen.getByLabelText(/Password/)).toHaveAttribute("type", "password");
    expect(screen.getByText(/explicit authorization to test it/i)).toBeInTheDocument();
  });

  it("submits login credentials only to the real login API", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ setup_required: false }))
      .mockResolvedValueOnce(
        jsonResponse(
          {
            detail: "Authentication is required.",
            code: "authentication_required",
          },
          401,
        ),
      )
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "preauth-csrf" }))
      .mockResolvedValueOnce(
        jsonResponse({
          user: {
            id: "user-1",
            email: "analyst@example.invalid",
            display_name: "Demo Analyst",
            role: "analyst",
            is_active: true,
            must_change_password: false,
          },
          csrf_token: "session-csrf",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderApp();

    await user.type(await screen.findByLabelText("Email address"), "analyst@example.invalid");
    await user.type(screen.getByLabelText("Password"), "not-a-real-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        "/api/v1/auth/login",
        expect.objectContaining({ method: "POST", credentials: "include" }),
      );
    });
    const loginCall = fetchMock.mock.calls.find(([path]) => path === "/api/v1/auth/login");
    expect(loginCall?.[1]?.body).toContain("analyst@example.invalid");
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.length).toBe(0);
  });
});
