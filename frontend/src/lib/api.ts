import { useLocation } from "react-router-dom";
import { normalizeWorkerUrl, type WorkerConnection } from "./connection";
import { useQuery } from "@tanstack/react-query";
import { getToken, useUI } from "./store";
import type { Evaluation, Health, Run } from "./types";
import { createApiClient } from "./client";
const request = createApiClient({
  onState: (connectionState) => useUI.setState({ connectionState }),
});
export async function api<T>(
  path: string,
  init?: RequestInit,
  connection: WorkerConnection = {
    url: useUI.getState().apiUrl,
    token: getToken(),
  },
): Promise<T> {
  const headers = new Headers(init?.headers);
  if (connection.token)
    headers.set("Authorization", `Bearer ${connection.token}`);
  return request<T>(normalizeWorkerUrl(connection.url), path, {
    ...init,
    headers,
  });
}
export const useHealth = () => {
  const url = useUI((s) => s.apiUrl);
  const revision = useUI((s) => s.connectionRevision);
  const connection = { url, token: getToken() };
  const playback = /^\/run\/(?:recording-|sample-)/.test(
    useLocation().pathname,
  );
  return useQuery({
    queryKey: ["health", url, revision],
    queryFn: ({ signal }) => api<Health>("/health", { signal }, connection),
    retry: false,
    enabled: !playback,
    refetchInterval: 30000,
  });
};
export const useRuns = () => {
  const health = useHealth();
  const url = useUI((s) => s.apiUrl);
  const revision = useUI((s) => s.connectionRevision);
  const connection = { url, token: getToken() };
  return useQuery({
    queryKey: ["runs", url, revision],
    queryFn: ({ signal }) => api<Run[]>("/runs", { signal }, connection),
    enabled: !!health.data?.database && !!connection.token,
    retry: false,
    refetchInterval: 6000,
  });
};
export const useEvaluation = () => {
  const health = useHealth();
  const url = useUI((s) => s.apiUrl);
  const revision = useUI((s) => s.connectionRevision);
  const connection = { url, token: getToken() };
  return useQuery({
    queryKey: ["evaluation", url, revision],
    queryFn: ({ signal }) => api<Evaluation>("/eval", { signal }, connection),
    enabled: !!health.data?.database && !!connection.token,
    retry: false,
  });
};
export const formatRepo = (url: string) =>
  url.replace("https://github.com/", "").replace(/\.git$/, "");
export function timeAgo(value: string) {
  const sec = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000);
  if (sec < 60) return "Just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}h ago`;
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}
export const elapsed = (start: string, end?: string | null) => {
  const sec = Math.max(
    0,
    Math.floor(
      ((end ? new Date(end).getTime() : Date.now()) -
        new Date(start).getTime()) /
        1000,
    ),
  );
  return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
};

export type Budget = {
  runner: string;
  current_concurrent_runs: number;
  queued_runs: number;
  github_queued_jobs: number | null;
  groq: Record<string, string> | null;
  github: Record<string, string> | null;
  max_concurrent_runs: number;
  max_attempts: number;
  test_timeout_seconds: number;
  note: string;
};
export const useLimits = () => {
  const health = useHealth();
  const url = useUI((s) => s.apiUrl);
  const revision = useUI((s) => s.connectionRevision);
  const connection = { url, token: getToken() };
  const playback = /^\/run\/(?:recording-|sample-)/.test(
    useLocation().pathname,
  );
  return useQuery({
    queryKey: ["limits", url, revision],
    queryFn: ({ signal }) => api<Budget>("/limits", { signal }, connection),
    enabled: !!health.data?.ready && !!connection.token && !playback,
    retry: false,
    refetchInterval: 30000,
  });
};

export type Recording = {
  id: string;
  repo_url: string;
  recorded_at: string;
  label: string;
};
export const useRecordings = () => {
  const url = useUI((s) => s.apiUrl);
  return useQuery({
    queryKey: ["recordings", url],
    queryFn: ({ signal }) =>
      api<Recording[]>("/replays", { signal }, { url, token: "" }),
    retry: false,
  });
};
