import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ConnectionDialog } from "./ConnectionDialog";
import { getToken, useUI } from "../lib/store";
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
beforeEach(() => {
  useUI.setState({
    apiUrl: "https://saved.example",
    connectionOpen: true,
    connectionRevision: 0,
  });
  sessionStorage.setItem("devpilot-api-token", "saved-worker-credential");
});
afterEach(() => {
  useUI.setState({ connectionOpen: false });
  vi.unstubAllGlobals();
});
function mount() {
  const query = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  query.setQueryData(["retained"], "existing history");
  render(
    <QueryClientProvider client={query}>
      <ConnectionDialog />
    </QueryClientProvider>,
  );
  return query;
}
it("keeps the saved worker and history when a candidate connection fails", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      expect(String(url).startsWith("https://candidate.example/")).toBe(true);
      if (String(url).endsWith("/health"))
        return json({ ready: true, database: true, runner: "github_actions" });
      expect(new Headers(init?.headers).get("Authorization")).toBe(
        "Bearer candidate-worker-credential",
      );
      return json({ detail: "Invalid worker access token" }, 401);
    }),
  );
  const user = userEvent.setup(),
    query = mount();
  await user.clear(screen.getByLabelText("API address"));
  await user.type(
    screen.getByLabelText("API address"),
    "https://candidate.example/api",
  );
  expect(
    (screen.getByLabelText("Worker access token") as HTMLInputElement).value,
  ).toBe("");
  await user.type(
    screen.getByLabelText("Worker access token"),
    "candidate-worker-credential",
  );
  await user.click(screen.getByRole("button", { name: "Test & save" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Invalid worker access token",
  );
  expect(useUI.getState().apiUrl).toBe("https://saved.example");
  expect(getToken()).toBe("saved-worker-credential");
  expect(query.getQueryData(["retained"])).toBe("existing history");
});
it("saves only after an authenticated check succeeds and drops the old cache", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL) =>
      String(url).endsWith("/health")
        ? json({
            ready: true,
            database: true,
            runner: "github_actions",
            runner_healthy: true,
            groq_configured: true,
          })
        : json({ max_concurrent_runs: 2 }),
    ),
  );
  const user = userEvent.setup(),
    query = mount();
  await user.clear(screen.getByLabelText("API address"));
  await user.type(
    screen.getByLabelText("API address"),
    "https://candidate.example/api/",
  );
  await user.type(
    screen.getByLabelText("Worker access token"),
    "candidate-worker-credential",
  );
  await user.click(screen.getByRole("button", { name: "Test & save" }));
  await screen.findByRole("status");
  expect(useUI.getState().apiUrl).toBe("https://candidate.example");
  expect(getToken()).toBe("candidate-worker-credential");
  expect(useUI.getState().connectionRevision).toBe(1);
  expect(query.getQueryData(["retained"])).toBeUndefined();
  expect(localStorage.getItem("devpilot-workspace-v1")).not.toContain(
    "candidate-worker-credential",
  );
});
it("can close an in-flight check without saving it", async () => {
  let abort: AbortSignal | null | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn((_url: RequestInfo | URL, init?: RequestInit) => {
      abort = init?.signal;
      return new Promise<Response>((_resolve, reject) =>
        abort?.addEventListener(
          "abort",
          () => reject(new DOMException("Cancelled", "AbortError")),
          { once: true },
        ),
      );
    }),
  );
  const user = userEvent.setup();
  mount();
  await user.click(screen.getByRole("button", { name: "Test & save" }));
  await screen.findByRole("button", { name: "Connecting…" });
  await user.click(screen.getByRole("button", { name: "Close" }));
  expect(abort?.aborted).toBe(true);
  expect(useUI.getState().apiUrl).toBe("https://saved.example");
  expect(getToken()).toBe("saved-worker-credential");
});
