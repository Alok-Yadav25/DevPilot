import { useQuery } from "@tanstack/react-query";
import { getToken, useUI } from "./store";
import type { Evaluation, Health, Run } from "./types";
import { createApiClient } from "./client";
const request = createApiClient({
  onState: (connectionState) => useUI.setState({ connectionState }),
});
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (getToken()) headers.set("Authorization", `Bearer ${getToken()}`);
  return request<T>(useUI.getState().apiUrl, path, { ...init, headers });
}
export const useHealth = () => {
  const url = useUI((s) => s.apiUrl);
  return useQuery({
    queryKey: ["health", url],
    queryFn: () => api<Health>("/health"),
    retry: false,
    enabled: !/^\/run\/(?:recording-|sample-)/.test(window.location.pathname),
    refetchInterval: 30000,
  });
};
export const useRuns = () => {
  const health = useHealth();
  const url = useUI((s) => s.apiUrl);
  return useQuery({
    queryKey: ["runs", url],
    queryFn: () => api<Run[]>("/runs"),
    enabled: !!health.data?.database,
    retry: false,
    refetchInterval: 6000,
  });
};
export const useEvaluation = () => {
  const health = useHealth();
  const url = useUI((s) => s.apiUrl);
  return useQuery({
    queryKey: ["evaluation", url],
    queryFn: () => api<Evaluation>("/eval"),
    enabled: !!health.data?.database,
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
  return useQuery({
    queryKey: ["limits", url],
    queryFn: () => api<Budget>("/limits"),
    enabled:
      !!health.data?.ready &&
      !/^\/run\/(?:recording-|sample-)/.test(window.location.pathname),
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
export const useRecordings = () =>
  useQuery({
    queryKey: ["recordings", useUI((s) => s.apiUrl)],
    queryFn: () => api<Recording[]>("/replays"),
    retry: false,
  });
