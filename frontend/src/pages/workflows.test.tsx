import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import { useUI } from "../lib/store";
import { advanceSample, makeSample } from "../lib/examples";
import NewRun from "./NewRun";
import LiveRun from "./LiveRun";
vi.mock("../components/AgentGraph", () => ({
  default: () => <div>Agent workflow diagram</div>,
}));
function mount(element: ReactNode, path = "/new") {
  const query = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={query}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/new" element={element} />
          <Route path="/run/:id" element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
beforeEach(() => {
  useUI.setState({ samples: [], apiUrl: "", connectionOpen: false });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockRejectedValue(new Error("Worker offline")),
  );
});
describe("Run and approval interactions", () => {
  it("prompts for a worker instead of fabricating a live run", async () => {
    const user = userEvent.setup();
    mount(<NewRun />);
    await user.type(
      screen.getByLabelText(/GitHub repository/),
      "https://github.com/owner/repo",
    );
    await user.type(
      screen.getByLabelText(/Bug description/),
      "The separator should be a hyphen.",
    );
    await user.click(screen.getByRole("button", { name: /Start run/ }));
    expect(useUI.getState().connectionOpen).toBe(true);
    expect(
      vi
        .mocked(fetch)
        .mock.calls.some(
          (c) => String(c[0]).endsWith("/runs") && c[1]?.method === "POST",
        ),
    ).toBe(false);
  });
  it("keeps approval disabled while the investigation is running", async () => {
    const sample = makeSample("slugify");
    useUI.setState({ samples: [sample] });
    mount(<LiveRun />, `/run/${sample.id}`);
    expect(
      (
        screen.getByRole("button", {
          name: /Approve patch/,
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
    expect(screen.getByText(/No live services/)).not.toBeNull();
  });
  it("records sample approval only after explicit confirmation", async () => {
    const user = userEvent.setup();
    let sample = makeSample("slugify");
    for (let i = 0; i < 20; i++) sample = advanceSample(sample);
    useUI.setState({ samples: [sample] });
    mount(<LiveRun />, `/run/${sample.id}`);
    await user.click(screen.getByRole("button", { name: /Approve patch/ }));
    expect(useUI.getState().samples[0].status).toBe("ready_for_review");
    await user.click(screen.getByRole("button", { name: "Confirm approval" }));
    await waitFor(() =>
      expect(useUI.getState().samples[0].status).toBe("completed"),
    );
    expect(useUI.getState().samples[0].pr_url).toBeUndefined();
    expect(
      vi.mocked(fetch).mock.calls.some((c) => c[1]?.method === "POST"),
    ).toBe(false);
  });
  it("switches the live output to the readable patch", async () => {
    const user = userEvent.setup();
    let sample = makeSample("clamp");
    for (let i = 0; i < 20; i++) sample = advanceSample(sample);
    useUI.setState({ samples: [sample] });
    mount(<LiveRun />, `/run/${sample.id}`);
    await user.click(screen.getByRole("tab", { name: "Diff" }));
    await waitFor(() => expect(screen.getByText("clamp.py")).not.toBeNull());
    expect(
      screen.getByRole("tab", { name: "Diff" }).getAttribute("aria-selected"),
    ).toBe("true");
  });
});

describe("calmer workspace", () => {
  it("reveals workflow only in its own tab", async () => {
    const user = userEvent.setup();
    const sample = makeSample("slugify");
    useUI.setState({ samples: [sample] });
    mount(<LiveRun />, `/run/${sample.id}`);
    expect(screen.queryByText("Agent workflow diagram")).toBeNull();
    await user.click(screen.getByRole("tab", { name: "Workflow" }));
    expect(await screen.findByText("Agent workflow diagram")).not.toBeNull();
  });
  it("brings the diff forward when review is ready", () => {
    let sample = makeSample("slugify");
    for (let i = 0; i < 20; i++) sample = advanceSample(sample);
    useUI.setState({ samples: [sample] });
    mount(<LiveRun />, `/run/${sample.id}`);
    expect(
      screen.getByRole("tab", { name: "Diff" }).getAttribute("aria-selected"),
    ).toBe("true");
    expect(
      screen.getByRole("heading", { name: "Review the patch" }),
    ).not.toBeNull();
  });
});
