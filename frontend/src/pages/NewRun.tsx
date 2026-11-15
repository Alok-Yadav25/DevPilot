import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import * as Switch from "@radix-ui/react-switch";
import { ArrowLeft, ArrowRight, Github, LoaderCircle } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { ExampleCards } from "../components/Examples";
import { api, useHealth } from "../lib/api";
import { getToken, useUI } from "../lib/store";
import type { Run } from "../lib/types";
export default function NewRun({ embedded = false }: { embedded?: boolean }) {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const query = useQueryClient();
  const [repo, setRepo] = useState(params.get("repo") ?? "");
  const currentRepo = useRef(repo);
  currentRepo.current = repo;
  const [issue, setIssue] = useState("");
  const [expected, setExpected] = useState("");
  const [dry, setDry] = useState(true);
  const [error, setError] = useState("");
  const [readiness, setReadiness] = useState("");
  const readinessCheck = useMutation({
    mutationFn: (requestedRepo: string) =>
      api<{ supported: string; repo_url: string }>("/repos/validate", {
        method: "POST",
        body: JSON.stringify({ repo_url: requestedRepo }),
      }),
    onSuccess: (data) => {
      const normalize = (url: string) =>
        url.replace(/\/$/, "").replace(/\.git$/, "");
      if (normalize(data.repo_url) === normalize(currentRepo.current))
        setReadiness("Repository checks passed. Tests run after you start.");
    },
    onError: (error, requestedRepo) => {
      if (requestedRepo === currentRepo.current) setReadiness(error.message);
    },
  });
  const health = useHealth();
  const connect = useUI((s) => s.setConnectionOpen);
  const mutation = useMutation({
    mutationFn: () =>
      api<Run>("/runs", {
        method: "POST",
        body: JSON.stringify({
          repo_url: repo,
          issue_text: issue,
          dry_run: dry,
          expected_failures: expected
            .split("\n")
            .map((x) => x.trim())
            .filter(Boolean),
        }),
      }),
    onSuccess: (run) => {
      query.invalidateQueries({ queryKey: ["runs"] });
      toast.success(
        run.status === "queued" ? "Run queued" : "Investigation started",
      );
      navigate(`/run/${run.id}`);
    },
    onError: (e) => setError(e.message),
  });
  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (mutation.isPending) return;
    setError("");
    if (
      !/^https:\/\/github\.com\/[A-Za-z0-9-]+\/[A-Za-z0-9_.-]+\/?$/.test(repo)
    ) {
      setError(
        "Use a GitHub repository URL such as https://github.com/owner/repo.",
      );
      return;
    }
    if (health.data?.runner === "replay") {
      setError(
        "This worker is in replay mode. Try an example or choose a recorded run.",
      );
      return;
    }
    if (!getToken()) {
      connect(true);
      return;
    }
    if (expected.split("\n").filter((line) => line.trim()).length > 20) {
      setError("Use at most 20 failing test IDs.");
      return;
    }
    mutation.mutate();
  }
  return (
    <div className={embedded ? "embedded-run" : "page new-run-page"}>
      {!embedded && (
        <>
          <Link className="back-link" to="/workspace">
            <ArrowLeft size={16} />
            Overview
          </Link>
          <header className="page-heading">
            <div>
              <h1>New run</h1>
            </div>
          </header>
        </>
      )}
      <div className="new-run-layout simple-run-layout">
        <form
          className="panel run-form"
          onSubmit={submit}
          aria-label="Start a run"
        >
          <fieldset className="run-fields" disabled={mutation.isPending}>
            <label className="field-label" htmlFor="repo">
              GitHub repository
            </label>
            <div className="input-with-icon">
              <Github size={17} />
              <input
                className="input"
                type="url"
                id="repo"
                required
                aria-describedby="repo-help"
                placeholder="https://github.com/owner/repository"
                value={repo}
                onChange={(e) => {
                  setRepo(e.target.value);
                  setReadiness("");
                }}
              />
              <button
                type="button"
                className="readiness-check"
                aria-label="Check repository readiness"
                disabled={!repo || readinessCheck.isPending}
                onClick={() => {
                  setReadiness("");
                  if (!getToken()) {
                    connect(true);
                    return;
                  }
                  readinessCheck.mutate(repo);
                }}
              >
                {readinessCheck.isPending ? "Checking…" : "Check"}
              </button>
            </div>
            <p className="field-help" id="repo-help">
              Public Python 3.11 repository with pytest.
            </p>
            {readiness && (
              <p
                role="status"
                className={`readiness-result ${readinessCheck.isError ? "text-error" : "text-success"}`}
              >
                {readiness}
              </p>
            )}
            <label className="field-label" htmlFor="issue">
              Bug description
            </label>
            <textarea
              className="input textarea"
              id="issue"
              required
              minLength={8}
              maxLength={16000}
              placeholder="Expected behavior, actual result, or a failing test."
              value={issue}
              onChange={(e) => setIssue(e.target.value)}
            />
            {issue.length > 14000 && (
              <div className="textarea-foot">
                <span>{issue.length.toLocaleString()} / 16,000</span>
              </div>
            )}
            <details className="advanced-options">
              <summary>Options</summary>
              <label className="field-label" htmlFor="expected">
                Failing tests <span>Optional</span>
              </label>
              <textarea
                className="input mono-input"
                rows={2}
                id="expected"
                maxLength={4000}
                spellCheck={false}
                placeholder="tests/test_example.py::test_behavior"
                value={expected}
                onChange={(e) => setExpected(e.target.value)}
              />
              <p className="field-help">
                One pytest node ID per line. Maximum 20.
              </p>
            </details>
            <div className="form-divider" />
            <div className="dry-run-control">
              <label htmlFor="dry-run">
                <strong>Dry run</strong>
                <small>No pull request.</small>
              </label>
              <Switch.Root
                className="switch"
                id="dry-run"
                aria-label="Dry run"
                checked={dry}
                onCheckedChange={setDry}
              >
                <Switch.Thumb className="switch-thumb" />
              </Switch.Root>
            </div>
            {!dry && (
              <p className="field-help">
                A draft PR opens only after your approval.
              </p>
            )}
            {error && (
              <div className="inline-error" role="alert">
                {error}
              </div>
            )}
            <div className="run-form-footer">
              <Button type="submit" disabled={mutation.isPending}>
                {mutation.isPending ? (
                  <LoaderCircle size={16} className="spin" />
                ) : null}
                {mutation.isPending ? "Starting…" : "Start run"}
                <ArrowRight size={16} />
              </Button>
            </div>
          </fieldset>
        </form>
      </div>
      {!embedded && (
        <details className="examples-disclosure">
          <summary>Try an example</summary>
          <p className="field-help">Illustrative samples. No live services.</p>
          <ExampleCards compact />
        </details>
      )}
    </div>
  );
}
