import { createApiClient } from "./client";
import type { Health } from "./types";

export type WorkerConnection = { url: string; token: string };
export function normalizeWorkerUrl(value: string): string {
  const input = value.trim();
  if (!input) return "";
  let url: URL;
  try {
    url = new URL(input);
  } catch {
    throw new Error("Enter a valid worker URL.");
  }
  if (
    !["http:", "https:"].includes(url.protocol) ||
    url.username ||
    url.password ||
    url.search ||
    url.hash
  )
    throw new Error(
      "Use an HTTP(S) worker URL without credentials, query parameters or fragments.",
    );
  if (
    url.protocol === "http:" &&
    !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)
  )
    throw new Error("Use HTTPS for a remote worker.");
  const path = url.pathname.replace(/\/+$/, "").replace(/\/api$/, "");
  return url.origin + path;
}
export async function probeConnection(
  connection: WorkerConnection,
  signal?: AbortSignal,
): Promise<Health> {
  const request = createApiClient();
  const headers = { Authorization: `Bearer ${connection.token}` };
  const health = await request<Health>(connection.url, "/health", { signal });
  if (
    !health ||
    typeof health.ready !== "boolean" ||
    !["github_actions", "docker", "replay"].includes(health.runner)
  )
    throw new Error("This address is not a DevPilot worker.");
  // Validate access before saving credentials or replacing a working connection.
  const limits = await request<{ max_concurrent_runs: number }>(
    connection.url,
    "/limits",
    { headers, signal },
  );
  if (typeof limits?.max_concurrent_runs !== "number")
    throw new Error("The worker returned an unsupported response.");
  return health;
}
