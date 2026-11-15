import { wait } from "./client";

/** Resumes SSE after dropped/idle connections; polling stays independent. */
export async function followEvents(
  url: string,
  options: {
    token: string;
    signal: AbortSignal;
    onEvent: () => void;
    onReconnect: (reconnecting: boolean) => void;
    idleMs?: number;
    retryMs?: number;
  },
): Promise<void> {
  let cursor = 0;
  while (!options.signal.aborted) {
    const connection = new AbortController();
    const stop = () => connection.abort();
    options.signal.addEventListener("abort", stop, { once: true });
    let idle: ReturnType<typeof setTimeout>;
    const heartbeat = () => {
      clearTimeout(idle);
      idle = setTimeout(stop, options.idleMs ?? 35000);
    };
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    heartbeat();
    try {
      const response = await fetch(url, {
        headers: {
          ...(options.token
            ? { Authorization: `Bearer ${options.token}` }
            : {}),
          ...(cursor ? { "Last-Event-ID": String(cursor) } : {}),
        },
        signal: connection.signal,
      });
      if ([401, 403, 404].includes(response.status)) return;
      if (
        !response.ok ||
        !response.body ||
        !response.headers.get("content-type")?.includes("text/event-stream")
      )
        throw new Error("Stream unavailable");
      options.onReconnect(false);
      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!connection.signal.aborted) {
        const { value, done } = await reader.read();
        if (done) break;
        heartbeat();
        buffer += decoder.decode(value, { stream: true });
        if (buffer.length > 256000) throw new Error("Stream frame too large");
        const frames = buffer.replaceAll("\r\n", "\n").split("\n\n");
        buffer = frames.pop() ?? "";
        for (const frame of frames) {
          const id = frame.match(/^id:\s*(\d+)\s*$/m);
          if (/^data:/m.test(frame) && (!id || Number(id[1]) > cursor))
            options.onEvent();
          if (id) cursor = Math.max(cursor, Number(id[1]));
          if (/^event:\s*settled\s*$/m.test(frame)) return;
        }
      }
    } catch {
      if (options.signal.aborted) return;
    } finally {
      clearTimeout(idle!);
      connection.abort();
      options.signal.removeEventListener("abort", stop);
      try {
        await reader?.cancel();
      } catch {
        /* Already disconnected. */
      }
      reader?.releaseLock();
    }
    if (options.signal.aborted) return;
    options.onReconnect(true);
    try {
      await wait(
        options.retryMs ?? 1500 + Math.random() * 1000,
        options.signal,
      );
    } catch {
      return;
    }
  }
}
