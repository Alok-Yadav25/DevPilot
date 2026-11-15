import { useState } from "react";
import {
  Cable,
  Check,
  ExternalLink,
  LoaderCircle,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Dialog } from "./ui/dialog";
import { Button } from "./ui/button";
import { getToken, setToken, useUI } from "../lib/store";
import { api } from "../lib/api";
import type { Health } from "../lib/types";
export function ConnectionDialog() {
  const { connectionOpen, setConnectionOpen, apiUrl, setApiUrl } = useUI();
  const [url, setUrl] = useState(apiUrl);
  const [token, changeToken] = useState(getToken());
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Health | null>(null);
  const [error, setError] = useState("");
  const query = useQueryClient();
  async function connect() {
    setBusy(true);
    setError("");
    try {
      const parsed = url ? new URL(url) : null;
      if (parsed && !["https:", "http:"].includes(parsed.protocol))
        throw new Error("Use an HTTP or HTTPS API address.");
      if (
        location.protocol === "https:" &&
        parsed?.protocol === "http:" &&
        !["localhost", "127.0.0.1"].includes(parsed.hostname)
      )
        throw new Error("Use an HTTPS worker address for this hosted website.");
      setApiUrl(url);
      setToken(token);
      const health = await api<Health>("/health");
      await api("/limits");
      setResult(health);
      await query.invalidateQueries();
      toast.success("Worker connection saved");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not connect.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={connectionOpen}
      onOpenChange={setConnectionOpen}
      title="Connect your worker"
      description="Connect your FastAPI worker. Provider credentials stay on the backend."
    >
      <div className="connection-note">
        <Terminal size={19} />
        <div>
          <strong>A small worker. A real sandbox.</strong>
          <p>
            Run the included FastAPI service locally or on your chosen provider.
            GitHub Actions runs the tests in a separate sandbox repository.
          </p>
        </div>
      </div>
      <label className="field-label" htmlFor="api-url">
        Worker API address
      </label>
      <input
        id="api-url"
        className="input"
        type="url"
        placeholder="https://your-worker.example.com"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
      />
      <p className="field-help">
        Leave empty for the local Vite proxy. Hosted connections need HTTPS and
        your Site origin in the worker’s CORS allowlist.
      </p>
      <label className="field-label" htmlFor="api-token">
        Worker access token
      </label>
      <input
        id="api-token"
        className="input"
        type="password"
        autoComplete="off"
        placeholder="The API_ACCESS_TOKEN from your backend"
        value={token}
        onChange={(e) => changeToken(e.target.value)}
      />
      <p className="field-help">
        Stored in this browser tab’s session. Never enter a GitHub token or Groq
        key here.
      </p>
      {error && (
        <div className="inline-error" role="alert">
          {error}
        </div>
      )}
      {result && (
        <div className="connection-checks">
          {[
            ["Database", result.database],
            [`${result.runner} runner`, result.runner_healthy],
            ["Groq key", result.groq_configured],
          ].map(([label, ok]) => (
            <div key={String(label)}>
              <span>{label}</span>
              <span className={ok ? "text-success" : "text-warning"}>
                {ok ? (
                  <>
                    <Check size={14} /> Ready
                  </>
                ) : (
                  "Needs setup"
                )}
              </span>
            </div>
          ))}
        </div>
      )}
      <div className="dialog-footer">
        <span className="muted flex-center">
          <ShieldCheck size={14} /> No keys in the sandbox
        </span>
        <Button onClick={connect} disabled={busy}>
          {busy ? (
            <LoaderCircle className="spin" size={15} />
          ) : (
            <Cable size={15} />
          )}
          Test connection
        </Button>
      </div>
      <a
        className="subtle-link"
        href="https://docs.github.com/en/actions"
        target="_blank"
        rel="noreferrer"
      >
        GitHub Actions setup guide <ExternalLink size={12} />
      </a>
    </Dialog>
  );
}
