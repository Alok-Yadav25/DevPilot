import { afterEach, expect, it, vi } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { makeSample } from "../lib/examples";
import { useUI, setToken } from "../lib/store";
import LiveRun from "./LiveRun";
import NewRun from "./NewRun";
vi.mock("../components/AgentGraph", () => ({ default: () => null }));
const json = (data: unknown) =>
  new Response(JSON.stringify(data), {
    headers: { "content-type": "application/json" },
  });
const health = { ready: true, database: true, runner: "github_actions" };
function client() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}
afterEach(() => {
  vi.unstubAllGlobals();
  useUI.setState({ apiUrl: "", samples: [] });
});
it("does not show a previous worker's run when URLs change", async () => {
  const query = client();
  useUI.setState({
    apiUrl: "https://first.example",
    connectionRevision: 0,
    samples: [],
  });
  setToken("first-local-worker");
  const first = {
    ...makeSample("slugify"),
    id: "same-id",
    mode: "live",
    status: "failed",
    repo_url: "https://github.com/first/project",
  };
  const second = { ...first, repo_url: "https://github.com/second/project" };
  query.setQueryData(["health", "https://first.example", 1], health);
  query.setQueryData(["run", "https://first.example", 1, "same-id"], first);
  let release: () => void = () => {};
  const delayed = new Promise<void>((resolve) => {
    release = resolve;
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).includes("/health")) return json(health);
      if (String(url).startsWith("https://second.example")) {
        expect(new Headers(init?.headers).get("Authorization")).toBe(
          "Bearer second-local-worker",
        );
        await delayed;
        return json(second);
      }
      return json(first);
    }),
  );
  render(
    <QueryClientProvider client={query}>
      <MemoryRouter initialEntries={["/run/same-id"]}>
        <Routes>
          <Route path="/run/:id" element={<LiveRun />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  expect(
    screen.getByRole("heading", { name: /first\/project/ }),
  ).not.toBeNull();
  act(() => {
    useUI.getState().setApiUrl("https://second.example");
    setToken("second-local-worker");
  });
  expect(screen.queryByRole("heading", { name: /first\/project/ })).toBeNull();
  await act(async () => release());
  expect(
    await screen.findByRole("heading", { name: /second\/project/ }),
  ).not.toBeNull();
});
it("sends multiline failing test IDs as separate selectors", async () => {
  useUI.setState({ apiUrl: "", samples: [] });
  setToken("local-worker-credential");
  let submitted: Record<string, unknown> | undefined;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).includes("lightweight")) return json({ status: "awake" });
      if (String(url).endsWith("/health")) return json(health);
      if (init?.method === "POST") {
        submitted = JSON.parse(String(init.body));
        return json({ id: "created", status: "queued" });
      }
      return json([]);
    }),
  );
  const user = userEvent.setup();
  render(
    <QueryClientProvider client={client()}>
      <MemoryRouter>
        <NewRun embedded />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  await user.type(
    screen.getByLabelText("GitHub repository"),
    "https://github.com/owner/project",
  );
  await user.type(
    screen.getByLabelText("Bug description"),
    "Fix the boundary error for both functions.",
  );
  await user.click(screen.getByText("Options"));
  await user.type(
    screen.getByLabelText(/Failing test/),
    "tests/test_math.py::test_one\ntests/test_math.py::test_two",
  );
  await user.click(screen.getByRole("button", { name: "Start run" }));
  await waitFor(() =>
    expect(submitted?.expected_failures).toEqual([
      "tests/test_math.py::test_one",
      "tests/test_math.py::test_two",
    ]),
  );
  expect(submitted?.dry_run).toBe(true);
});
