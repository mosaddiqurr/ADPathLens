import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectPage } from "../src/pages/ProjectPage";

function response(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const project = {
  id: "project-1",
  name: "Project One",
  description: "Synthetic project.",
  status: "active",
  created_at: "2026-07-30T00:00:00Z",
  updated_at: "2026-07-30T00:00:00Z",
};

const target = {
  id: "target-1",
  project_id: "project-1",
  name: "Demo target",
  base_url: "http://127.0.0.1:8021",
  hostname: "127.0.0.1",
  port: 8021,
  authorization_confirmed: true,
  lab_network_confirmed: true,
  allow_private_networks: true,
  allowed_path_prefixes: ["/"],
  allowed_methods: ["GET"],
  request_budget: 25,
  request_count_used: 2,
  maximum_response_bytes: 2_097_152,
  last_execution_at: null,
  concurrency_limit: 2,
  authorization_expires_at: null,
  tls_policy: "strict",
  state_changes_enabled: false,
  local_test_target: true,
  is_active: true,
};

function workspaceFetch(path: string): Response {
  if (path.endsWith("/projects/project-1")) return response(project);
  if (path.endsWith("/projects/project-1/targets")) return response([target]);
  if (path.endsWith("/projects/project-1/sessions")) {
    return response([
      {
        id: "profile-1",
        project_id: "project-1",
        target_id: "target-1",
        name: "Masked User",
        role_label: "user",
        description: "",
        secret_fingerprint: "hmac:1234567890ab",
        is_anonymous: false,
        is_active: true,
        credential_version: 1,
        expires_at: null,
      },
    ]);
  }
  if (path.includes("/request-collections")) return response([]);
  if (path.endsWith("/projects/project-1/requests")) return response([]);
  if (path.includes("/test-cases")) return response([]);
  if (path.endsWith("/projects/project-1/runs")) return response([]);
  if (path.endsWith("/projects/project-1/findings")) return response([]);
  if (path.endsWith("/projects/project-1/reports")) return response([]);
  return response({ detail: "Not found", code: "not_found" }, 404);
}

function requestPath(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.toString();
  return input.url;
}

function renderProject(section: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/projects/project-1/${section}`]}>
        <Routes>
          <Route path="/projects/:projectId/:section" element={<ProjectPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Project workflows", () => {
  it("shows only masked profile metadata and uses password inputs for replacement", async () => {
    const fetchMock = vi.fn<typeof fetch>((input) =>
      Promise.resolve(workspaceFetch(requestPath(input))),
    );
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderProject("profiles");

    expect(await screen.findByRole("cell", { name: "Masked User" })).toBeInTheDocument();
    expect(screen.getByText("hmac:1234567890ab")).toBeInTheDocument();
    expect(screen.queryByText("demo-user-a-token")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Manage" }));
    expect(screen.getByLabelText("Replacement authorization value")).toHaveAttribute(
      "type",
      "password",
    );
    expect(screen.getByLabelText("Replacement cookie header")).toHaveAttribute(
      "type",
      "password",
    );
  });

  it("submits cURL text to the parser endpoint without executing it", async () => {
    const fetchMock = vi.fn<typeof fetch>((input) =>
      Promise.resolve(workspaceFetch(requestPath(input))),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderProject("requests");

    expect(await screen.findByRole("heading", { name: "Safe cURL import" })).toBeVisible();
    expect(screen.getByLabelText("cURL command")).toBeInstanceOf(HTMLTextAreaElement);
    expect(screen.getByText(/parsed as text and never executed/i)).toBeVisible();
  });
});
