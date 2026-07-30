export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
  }
}

export interface Problem {
  detail?: string;
  code?: string;
}

let csrfToken: string | null = null;

export function setCsrfToken(token: string | null): void {
  csrfToken = token;
}

export async function refreshCsrf(): Promise<string> {
  const value = await api<{ csrf_token: string }>("/auth/csrf");
  setCsrfToken(value.csrf_token);
  return value.csrf_token;
}

export function jsonBody(value: unknown): Pick<RequestInit, "body"> {
  return { body: JSON.stringify(value) };
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (init.method && !["GET", "HEAD", "OPTIONS"].includes(init.method.toUpperCase()) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as Problem;
    throw new ApiError(
      problem.detail ?? "The request could not be completed.",
      response.status,
      problem.code ?? "request_failed",
    );
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
