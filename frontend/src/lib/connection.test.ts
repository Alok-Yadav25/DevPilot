import { afterEach, describe, expect, it, vi } from "vitest";
import { normalizeWorkerUrl, probeConnection } from "./connection";
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json" },
  });
afterEach(() => vi.unstubAllGlobals());
describe("worker addresses", () => {
  it("normalizes pasted API addresses and local proxy", () => {
    expect(normalizeWorkerUrl(" https://worker.example/api/ ")).toBe(
      "https://worker.example",
    );
    expect(normalizeWorkerUrl("https://worker.example/backend/")).toBe(
      "https://worker.example/backend",
    );
    expect(normalizeWorkerUrl("")).toBe("");
    expect(normalizeWorkerUrl("http://[::1]:8000/api")).toBe(
      "http://[::1]:8000",
    );
  });
  it.each([
    "javascript:alert(1)",
    "https://user:password@worker.example",
    "https://worker.example?token=private",
    "https://worker.example#token",
    "http://worker.example",
  ])("rejects unsafe address %s", (url) =>
    expect(() => normalizeWorkerUrl(url)).toThrow(),
  );
  it("tests a candidate without replacing saved credentials", async () => {
    sessionStorage.setItem("devpilot-api-token", "original-local-credential");
    const fetcher = vi.fn(
      async (url: RequestInfo | URL, init?: RequestInit) => {
        if (String(url).endsWith("/health"))
          return json({
            ready: true,
            database: true,
            runner: "github_actions",
          });
        expect(new Headers(init?.headers).get("Authorization")).toBe(
          "Bearer candidate-local-credential",
        );
        return json({ detail: "Wrong token" }, 401);
      },
    );
    vi.stubGlobal("fetch", fetcher);
    await expect(
      probeConnection({
        url: "https://candidate.example",
        token: "candidate-local-credential",
      }),
    ).rejects.toThrow("Wrong token");
    expect(sessionStorage.getItem("devpilot-api-token")).toBe(
      "original-local-credential",
    );
  });
});
