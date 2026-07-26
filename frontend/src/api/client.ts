export type Problem = {
  title: string;
  detail: string;
  status: number;
  code?: string;
  request_id?: string;
  errors?: Array<{ location: string; message: string; code: string }>;
};

export class ApiError extends Error {
  problem: Problem;

  constructor(problem: Problem) {
    super(problem.detail);
    this.name = "ApiError";
    this.problem = problem;
  }
}

let csrfToken = "";

export function setCsrfToken(value: string) {
  csrfToken = value;
}

export async function api<T>(
  path: string,
  options: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  let body = options.body;
  if (options.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.json);
  }
  const method = (options.method ?? "GET").toUpperCase();
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    body,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    const fallback: Problem = {
      title: "Request failed",
      detail: `${response.status} ${response.statusText}`,
      status: response.status,
    };
    const problem = (await response.json().catch(() => fallback)) as Problem;
    throw new ApiError(problem);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.problem.detail : "The request could not be completed.";
}

