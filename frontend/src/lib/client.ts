export type ConnectionState =
  "connected" | "waking" | "reconnecting" | "offline" | "error";
export type ErrorKind =
  | "network"
  | "offline"
  | "rate_limited"
  | "server"
  | "validation"
  | "connection";
export class ApiError extends Error {
  constructor(
    message: string,
    public kind: ErrorKind,
    public status = 0,
    public retryAfter?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export function wait(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted)
      return reject(new DOMException("Cancelled", "AbortError"));
    const stop = () => {
      clearTimeout(timer);
      reject(new DOMException("Cancelled", "AbortError"));
    };
    const timer = setTimeout(() => {
      signal?.removeEventListener("abort", stop);
      resolve();
    }, ms);
    signal?.addEventListener("abort", stop, { once: true });
  });
}
export function createApiClient(
  options: {
    fetcher?: typeof fetch;
    timeoutMs?: number;
    wakeMs?: number;
    onState?: (state: ConnectionState) => void;
  } = {},
) {
  const fetcher: typeof fetch = (...args) =>
    (options.fetcher ?? fetch)(...args);
  const timeout = options.timeoutMs ?? 10000;
  const wakeMs = options.wakeMs ?? 90000;
  const wakes = new Map<string, Promise<void>>();
  const successes = new Map<string, number>();
  async function timed(url: string, init: RequestInit, budget = timeout) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (init.signal?.aborted) abort();
    init.signal?.addEventListener("abort", abort, { once: true });
    const timer = setTimeout(abort, budget);
    try {
      return await fetcher(url, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timer);
      init.signal?.removeEventListener("abort", abort);
    }
  }
  async function wake(base: string, deadline: number) {
    let attempt = 0;
    while (Date.now() < deadline) {
      try {
        const response = await timed(
          `${base}/api/health?lightweight=true`,
          {},
          Math.min(timeout, deadline - Date.now()),
        );
        if (
          response.ok &&
          response.headers.get("content-type")?.includes("application/json")
        ) {
          const data = await response.json();
          if (data.status === "awake") return;
        }
      } catch {
        /* Try again within the same finite wake budget. */
      }
      await wait(
        Math.max(
          0,
          Math.min(
            deadline - Date.now(),
            Math.min(8000, 1000 * 2 ** attempt++) * (0.8 + Math.random() * 0.4),
          ),
        ),
      );
    }
    throw new ApiError(
      "The server has not responded yet. Check the API address and try again shortly.",
      "connection",
    );
  }
  return async function request<T>(
    base: string,
    path: string,
    init: RequestInit = {},
  ): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Content-Type", "application/json");
    if (
      path === "/runs" &&
      init.method === "POST" &&
      !headers.has("Idempotency-Key")
    )
      headers.set("Idempotency-Key", crypto.randomUUID().replaceAll("-", ""));
    const prepared = { ...init, headers };
    const deadline = Date.now() + wakeMs;
    let response: Response;
    try {
      response = await timed(`${base}/api${path}`, prepared);
      if (
        [502, 504].includes(response.status) ||
        (response.status === 503 &&
          !response.headers.get("content-type")?.includes("application/json"))
      )
        throw new TypeError("Server is waking");
    } catch (error) {
      if (init.signal?.aborted) throw error;
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        options.onState?.("offline");
        throw new ApiError(
          "You are offline. Reconnect to the internet, then retry.",
          "offline",
        );
      }
      options.onState?.(
        !successes.has(base) ||
          Date.now() - (successes.get(base) ?? 0) > 15 * 60000
          ? "waking"
          : "reconnecting",
      );
      let pending = wakes.get(base);
      if (!pending) {
        pending = wake(base, deadline).finally(() => wakes.delete(base));
        wakes.set(base, pending);
      }
      try {
        await pending;
        if (init.signal?.aborted)
          throw new DOMException("Cancelled", "AbortError");
        response = await timed(`${base}/api${path}`, prepared);
      } catch (failure) {
        options.onState?.("error");
        if (failure instanceof ApiError) throw failure;
        throw new ApiError(
          "The connection was interrupted. Check the worker and retry.",
          "connection",
        );
      }
    }
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new ApiError(
        "The API address did not return JSON. Check the worker URL and CORS allowlist.",
        "connection",
        response.status,
      );
    const data = await response.json();
    successes.set(base, Date.now());
    options.onState?.("connected");
    if (!response.ok) {
      const detail =
        typeof data.detail === "string"
          ? data.detail
          : Array.isArray(data.detail)
            ? data.detail.map((e: { msg?: string }) => e.msg).join(". ")
            : "The server could not complete this request. Check worker health and retry.";
      throw new ApiError(
        detail,
        response.status === 429
          ? "rate_limited"
          : response.status >= 500
            ? "server"
            : "validation",
        response.status,
        response.headers.get("retry-after") ?? undefined,
      );
    }
    return data as T;
  };
}
