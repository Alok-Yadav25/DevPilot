import { useEffect, useRef, useState } from "react";
import { Check, LoaderCircle } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Dialog } from "./ui/dialog";
import { Button } from "./ui/button";
import { getToken, saveConnection, useUI } from "../lib/store";
import { normalizeWorkerUrl, probeConnection } from "../lib/connection";
import type { Health } from "../lib/types";
export function ConnectionDialog() {
  const open = useUI((s) => s.connectionOpen);
  const setOpen = useUI((s) => s.setConnectionOpen);
  const [url, setUrl] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Health | null>(null);
  const [error, setError] = useState("");
  const pending = useRef<AbortController | null>(null);
  const query = useQueryClient();
  useEffect(() => {
    if (open) {
      setUrl(useUI.getState().apiUrl);
      setToken(getToken());
      setResult(null);
      setError("");
    } else pending.current?.abort();
    return () => pending.current?.abort();
  }, [open]);
  async function connect(event: React.FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    setResult(null);
    const controller = new AbortController();
    pending.current = controller;
    try {
      const address = normalizeWorkerUrl(url);
      if (!token.trim()) throw new Error("Enter your worker access token.");
      const health = await probeConnection(
        { url: address, token: token.trim() },
        controller.signal,
      );
      if (controller.signal.aborted) return;
      await query.cancelQueries();
      if (controller.signal.aborted) return;
      query.clear();
      saveConnection(address, token.trim());
      setResult(health);
      toast.success("Connection saved");
    } catch (failure) {
      if (!controller.signal.aborted)
        setError(
          failure instanceof Error
            ? failure.message
            : "Connection failed. Check the address and token.",
        );
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={setOpen}
      title="Worker connection"
      description="Connect your backend to run real repairs."
    >
      <form onSubmit={connect}>
        <fieldset disabled={busy} className="connection-fields">
          <label className="field-label" htmlFor="api-url">
            API address
          </label>
          <input
            id="api-url"
            className="input"
            type="url"
            placeholder="http://localhost:8000"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              setToken("");
              setResult(null);
              setError("");
            }}
          />
          <p className="field-help">Leave blank to use the local proxy.</p>
          <label className="field-label" htmlFor="api-token">
            Worker access token
          </label>
          <input
            id="api-token"
            className="input"
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => {
              setToken(e.target.value);
              setResult(null);
              setError("");
            }}
          />
          <p className="field-help">
            Session only. Use API_ACCESS_TOKEN, never a GitHub or Groq key.
          </p>
          {error && (
            <p className="inline-error" role="alert">
              {error}
            </p>
          )}
          {result && (
            <div className="connection-checks" role="status">
              {[
                ["Database", result.database],
                ["Test runner", result.runner_healthy],
                ["Model", result.groq_configured || result.runner === "replay"],
              ].map(([label, ok]) => (
                <div key={String(label)}>
                  <span>{label}</span>
                  <span className={ok ? "text-success" : "text-warning"}>
                    {ok ? (
                      <>
                        <Check size={14} />
                        Ready
                      </>
                    ) : (
                      "Needs setup"
                    )}
                  </span>
                </div>
              ))}
              {!result.ready && <p className="field-help">{result.message}</p>}
            </div>
          )}
        </fieldset>
        <div className="dialog-footer">
          <Button
            variant="secondary"
            type="button"
            onClick={() => setOpen(false)}
          >
            Close
          </Button>
          <Button type="submit" disabled={busy}>
            {busy && <LoaderCircle size={16} className="spin" />}
            {busy ? "Connecting…" : "Test & save"}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
