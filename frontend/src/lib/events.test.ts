import { afterEach, expect, it, vi } from "vitest";
import { followEvents } from "./events";
function response(text: string) {
  return new Response(new TextEncoder().encode(text), {
    headers: { "content-type": "text/event-stream" },
  });
}
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
it("resumes dropped streams with the last event ID and ignores duplicates", async () => {
  const controller = new AbortController(),
    event = vi.fn();
  let count = 0;
  const fetcher = vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
    if (count++ === 0)
      return response("id: 7\r\nevent: step\r\ndata: {}\r\n\r\n");
    expect(new Headers(init?.headers).get("Last-Event-ID")).toBe("7");
    return response(
      "id: 7\nevent: step\ndata: {}\n\nid: 8\nevent: step\ndata: {}\n\nevent: settled\ndata: {}\n\n",
    );
  });
  vi.stubGlobal("fetch", fetcher);
  await followEvents("https://worker.example/api/runs/one/events", {
    token: "local-worker-credential",
    signal: controller.signal,
    onEvent: event,
    onReconnect: () => {},
    retryMs: 0,
  });
  expect(fetcher).toHaveBeenCalledTimes(2);
  expect(event).toHaveBeenCalledTimes(3);
});
it("reconnects a silent stream after its heartbeat deadline", async () => {
  vi.useFakeTimers();
  const controller = new AbortController();
  let count = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) => {
      if (count++ > 0) return response("event: settled\ndata: {}\n\n");
      const stream = new ReadableStream<Uint8Array>({
        start(streamController) {
          init?.signal?.addEventListener(
            "abort",
            () =>
              streamController.error(
                new DOMException("Disconnected", "AbortError"),
              ),
            { once: true },
          );
        },
      });
      return new Response(stream, {
        headers: { "content-type": "text/event-stream" },
      });
    }),
  );
  const reconnect = vi.fn();
  const done = followEvents("https://worker.example/events", {
    token: "",
    signal: controller.signal,
    onEvent: () => {},
    onReconnect: reconnect,
    idleMs: 1000,
    retryMs: 1,
  });
  await vi.advanceTimersByTimeAsync(1100);
  await done;
  expect(reconnect).toHaveBeenCalledWith(true);
  expect(count).toBe(2);
});
