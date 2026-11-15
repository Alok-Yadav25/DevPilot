import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, createApiClient } from "./client";
const json = (data: unknown, status = 200, headers = {}) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json", ...headers },
  });
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});
describe("API connection recovery", () => {
  it("waits through a 60 second cold start and resumes the action", async () => {
    vi.useFakeTimers();
    const started = Date.now();
    const states: string[] = [];
    const fetcher = vi.fn(async (url: string | URL | Request) => {
      if (Date.now() - started < 60000) throw new TypeError("sleeping");
      return String(url).includes("lightweight")
        ? json({ status: "awake" })
        : json({ id: "real-record" });
    });
    const request = createApiClient({
      fetcher: fetcher as typeof fetch,
      onState: (state) => states.push(state),
    });
    const pending = request("https://worker.test", "/runs/one");
    await vi.advanceTimersByTimeAsync(75000);
    await expect(pending).resolves.toEqual({ id: "real-record" });
    expect(states).toContain("waking");
    expect(states.at(-1)).toBe("connected");
  });
  it("preserves the run idempotency key across a connection retry", async () => {
    const keys: string[] = [];
    let first = true;
    const fetcher = vi.fn(
      async (url: string | URL | Request, init?: RequestInit) => {
        if (String(url).includes("lightweight"))
          return json({ status: "awake" });
        keys.push(new Headers(init?.headers).get("Idempotency-Key")!);
        if (first) {
          first = false;
          throw new TypeError("lost response");
        }
        return json({ id: "one" });
      },
    ) as typeof fetch;
    await createApiClient({ fetcher })("", "/runs", {
      method: "POST",
      body: "{}",
    });
    expect(keys).toHaveLength(2);
    expect(keys[0]).toMatch(/^[a-f0-9]{32}$/);
    expect(keys[0]).toBe(keys[1]);
  });
  it.each([
    [429, "rate_limited"],
    [422, "validation"],
    [503, "server"],
  ])("classifies HTTP %s without resubmitting", async (status, kind) => {
    const fetcher = vi.fn(async () =>
      json({ detail: "Actionable explanation" }, Number(status), {
        "retry-after": "12",
      }),
    );
    await expect(
      createApiClient({ fetcher })("", "/runs"),
    ).rejects.toMatchObject({
      kind,
      message: "Actionable explanation",
      retryAfter: "12",
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("stops waiting after the wake budget", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockRejectedValue(new TypeError("offline server"));
    const result = createApiClient({ fetcher, wakeMs: 90000 })(
      "",
      "/runs",
    ).catch((error) => error);
    await vi.advanceTimersByTimeAsync(91000);
    expect(await result).toBeInstanceOf(ApiError);
    expect(((await result) as ApiError).kind).toBe("connection");
  });
});

it("does not retry a slow but valid run-readiness request", async () => {
  vi.useFakeTimers();
  const fetcher = vi.fn(async (url: string | URL | Request) => {
    if (String(url).includes("lightweight")) return json({ status: "awake" });
    await new Promise((resolve) => setTimeout(resolve, 55000));
    return json({ id: "one-created-run" });
  });
  const result = createApiClient({ fetcher })("", "/runs", {
    method: "POST",
    body: "{}",
  });
  await vi.advanceTimersByTimeAsync(56000);
  await expect(result).resolves.toEqual({ id: "one-created-run" });
  expect(fetcher).toHaveBeenCalledTimes(2); // One cheap probe, one mutation.
});
