/** Public API origin, supplied when building for a static host. */
export function apiUrl(path: string): string {
  const origin = (import.meta.env.VITE_API_URL ?? "")
    .trim()
    .replace(/\/+$/, "");
  return `${origin}/api/v1${path}`;
}
