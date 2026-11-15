import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import * as Switch from "@radix-ui/react-switch";
import {
  ArrowLeft,
  ArrowRight,
  Code2,
  Github,
  Info,
  LoaderCircle,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  Zap,
} from "lucide-react";
import { motion } from "framer-motion";
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
    mutationFn: () =>
      api<{ supported: string; repo_url: string }>("/repos/validate", {
        method: "POST",
        body: JSON.stringify({ repo_url: repo }),
      }),
    onSuccess: (data) => {
      const normalize = (url: string) =>
        url.replace(/\/$/, "").replace(/\.git$/, "");
      if (normalize(data.repo_url) === normalize(currentRepo.current))
        setReadiness(
          `Ready for ${data.supported}. The runner still checks installation and tests.`,
        );
    },
    onError: (error) => setReadiness(error.message),
  });
  const health = useHealth();
  const connected = health.data?.ready;
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
    if (!connected && !getToken()) {
      connect(true);
      return;
    }
    mutation.mutate();
  }
  return (
    <motion.div
      className={embedded ? "embedded-run" : "page new-run-page"}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
    >
      {!embedded && (
        <>
          <Link className="back-link" to="/">
            <ArrowLeft size={14} />
            Back to overview
          </Link>
          <div className="page-heading">
            <div>
              <div className="eyebrow">GIVE YOUR AGENT A MISSION</div>
              <h1>
                A bug in. A reviewable fix out
                <span className="heading-dot">.</span>
              </h1>
              <p>A little context is all it takes to get started.</p>
            </div>
            <span className="heading-chip">
              <Code2 size={14} />
              Python + pytest
            </span>
          </div>
        </>
      )}
      <div className="new-run-layout">
        <form className="panel run-form" onSubmit={submit}>
          {!embedded && (
            <div className="form-section-title">
              <span className="number-circle">01</span>
              <h2>Point us at the problem</h2>
            </div>
          )}
          <label className="field-label" htmlFor="repo">
            GitHub repository<span>Required</span>
          </label>
          <div className="input-with-icon">
            <Github size={17} />
            <input
              className="input"
              type="url"
              id="repo"
              required
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
              disabled={!repo || readinessCheck.isPending}
              onClick={() => {
                setReadiness("");
                readinessCheck.mutate();
              }}
            >
              {readinessCheck.isPending ? "Checking…" : "Check readiness"}
            </button>
          </div>
          {readiness && (
            <p
              role="status"
              className={`readiness-result ${readinessCheck.isError ? "text-error" : "text-success"}`}
            >
              {readiness}
            </p>
          )}
          <p className="field-help">
            A Python repository with pytest and requirements.txt or
            pyproject.toml.
          </p>
          <label className="field-label" htmlFor="issue">
            What’s going wrong?<span>Required</span>
          </label>
          <textarea
            className="input textarea"
            id="issue"
            required
            minLength={8}
            maxLength={16000}
            placeholder="Describe the expected behavior, what happens instead, and how to reproduce it. A failing test name or traceback helps."
            value={issue}
            onChange={(e) => setIssue(e.target.value)}
          />
          <div className="textarea-foot">
            <span>Clear context makes for a better fix.</span>
            <span>{issue.length.toLocaleString()} / 16,000</span>
          </div>
          <details className="advanced-options">
            <summary>Advanced options</summary>
            <label className="field-label" htmlFor="expected">
              Expected failing tests<span>Optional</span>
            </label>
            <input
              className="input mono-input"
              id="expected"
              placeholder="tests/test_example.py::test_expected_behavior"
              value={expected}
              onChange={(e) => setExpected(e.target.value)}
            />
            <p className="field-help">
              An exact test ID helps the agent stop if unrelated tests fail.
            </p>
          </details>
          <div className="form-divider" />
          <div className="dry-run-control">
            <span className="dry-run-icon">
              <ShieldCheck size={21} />
            </span>
            <label htmlFor="dry-run">
              <strong>Dry run</strong>
              <small>
                Generate and test a patch without opening a pull request.
              </small>
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
            <div className="notice">
              <LockKeyhole size={16} />
              <span>
                DevPilot will still wait for your explicit approval before
                pushing a target branch or opening a PR.
              </span>
            </div>
          )}
          {!connected && (
            <div className="worker-notice">
              <span className="status-dot amber" />
              <span>A worker is needed for live runs.</span>
              <button type="button" onClick={() => connect(true)}>
                Connect worker
                <ArrowRight size={13} />
              </button>
            </div>
          )}
          {error && (
            <div className="inline-error" role="alert">
              {error}
            </div>
          )}
          <div className="run-form-footer">
            <span>
              <LockKeyhole size={13} />
              Your repository stays yours.
            </span>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? (
                <LoaderCircle size={16} className="spin" />
              ) : (
                <Zap size={16} />
              )}
              Start run
              <ArrowRight size={15} />
            </Button>
          </div>
        </form>
        {!embedded && (
          <aside className="run-explainer">
            <div className="panel">
              <span className="explainer-icon">
                <Sparkles size={22} />
              </span>
              <h3>Here’s what happens next</h3>
              <p>Your agent works through a deliberate, visible process.</p>
              <ol>
                {[
                  ["Reproduce", "Clone the repo and run the baseline twice."],
                  [
                    "Investigate",
                    "Trace the failure and explain the likely cause.",
                  ],
                  ["Patch & test", "Make a small change. Run the full suite."],
                  ["Hand it back", "You review the diff, evidence, and risks."],
                ].map(([title, description], i) => (
                  <li key={title}>
                    <span>{i + 1}</span>
                    <div>
                      <strong>{title}</strong>
                      <p>{description}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <div className="explainer-footer">
                <ShieldCheck size={17} />
                <span>
                  Tests run offline. No secrets.
                  <br />
                  No automatic merge.
                </span>
              </div>
            </div>
            <div className="expectations">
              <Info size={16} />
              <p>
                Best for small, reproducible Python bugs. Network-dependent
                tests stop with a clear explanation. Actions dependency
                preparation uses public downloads before test networking is
                disabled.
              </p>
            </div>
          </aside>
        )}
      </div>
      {!embedded && (
        <section className="examples-section">
          <div className="section-heading">
            <div>
              <h2>Just looking around?</h2>
              <p>
                Try an interactive example. No repository access or API key
                needed.
              </p>
            </div>
          </div>
          <ExampleCards compact />
        </section>
      )}
    </motion.div>
  );
}
