import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowDown,
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Clock3,
  Code2,
  Copy,
  ExternalLink,
  FileCode2,
  FlaskConical,
  GitBranch,
  GitPullRequest,
  Github,
  Info,
  LoaderCircle,
  LockKeyhole,
  Pause,
  Play,
  RotateCcw,
  ShieldCheck,
  Square,
  Terminal,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Dialog } from "../components/ui/dialog";
import { activityStatus, StatusBadge } from "../components/StatusBadge";
import { api, elapsed, formatRepo, useHealth } from "../lib/api";
import { getToken, useUI } from "../lib/store";
import { makeRecorded } from "../lib/replay";
import { makeSample } from "../lib/examples";
import { normalizeWorkerUrl } from "../lib/connection";
import { followEvents } from "../lib/events";
import { STEPS, type Run, type RunEvent } from "../lib/types";
import { FailureExplanation, ReviewChecklist } from "../components/RunReview";
import { CompareAttempts } from "../components/CompareAttempts";
const AgentGraph = lazy(() => import("../components/AgentGraph"));
export async function diffHash(diff: string) {
  const bytes = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(diff),
  );
  return [...new Uint8Array(bytes)]
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
}
async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  } catch {
    toast.error("Clipboard access is unavailable in this browser.");
  }
}
const PatchViewer = lazy(() => import("../components/PatchViewer"));
function Diff({ diff }: { diff: string }) {
  return diff ? (
    <Suspense fallback={<div className="skeleton skeleton-card" />}>
      <PatchViewer diff={diff} />
    </Suspense>
  ) : (
    <div className="tab-empty">
      <FileCode2 size={27} />
      <strong>The patch will appear here</strong>
      <p>The agent validates every edit before running the tests.</p>
    </div>
  );
}

function Logs({ events }: { events: RunEvent[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pinned, setPinned] = useState(true);
  useEffect(() => {
    if (pinned && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [events.length, pinned]);
  return (
    <div className="logs-container">
      <div
        className="logs-view"
        ref={ref}
        onScroll={() => {
          if (ref.current)
            setPinned(
              ref.current.scrollHeight -
                ref.current.scrollTop -
                ref.current.clientHeight <
                55,
            );
        }}
        aria-live="polite"
        aria-relevant="additions"
      >
        {events.length ? (
          events.map((event, i) => (
            <div className={`log-line log-${event.type}`} key={event.id ?? i}>
              <span className="log-time">
                {new Date(event.timestamp).toLocaleTimeString("en-GB", {
                  hour12: false,
                })}
              </span>
              <span className="log-marker">
                {event.type === "end" ? (
                  <Check size={12} />
                ) : event.type === "error" ? (
                  <X size={12} />
                ) : (
                  <ChevronRight size={12} />
                )}
              </span>
              <div>
                <span className="log-node">{event.node}</span>
                <p>{event.message}</p>
              </div>
            </div>
          ))
        ) : (
          <div className="tab-empty">
            <Terminal size={27} />
            <strong>Listening for your agent</strong>
            <p>Events will stream here as the investigation begins.</p>
          </div>
        )}
      </div>
      {!pinned && (
        <button className="jump-latest" onClick={() => setPinned(true)}>
          <ArrowDown size={12} />
          Jump to latest
        </button>
      )}
    </div>
  );
}
function Tests({ run }: { run: Run }) {
  const result = run.attempts.at(-1)?.test_result;
  const baseline = run.baseline_result;
  const outcome = result ?? baseline;
  if (!outcome)
    return (
      <div className="tab-empty">
        <FlaskConical size={27} />
        <strong>Waiting for test evidence</strong>
        <p>The suite runs twice before the first change.</p>
      </div>
    );
  const passed = Object.values(outcome.outcomes).filter(
    (x) => x === "passed",
  ).length;
  const failed = Object.values(outcome.outcomes).filter(
    (x) => x === "failed",
  ).length;
  return (
    <div className="tests-tab">
      <div className="tests-summary">
        <div className="text-success">
          <strong>{passed}</strong>
          <span>Passed</span>
        </div>
        <div className="text-error">
          <strong>{failed}</strong>
          <span>Failed</span>
        </div>
        <div>
          <strong>
            {outcome.duration_seconds?.toFixed(2) ?? "—"}
            <small>s</small>
          </strong>
          <span>Duration</span>
        </div>
      </div>
      <span className="section-caption">
        {result ? "LATEST PATCH RESULT" : "BASELINE RESULT"}
        {run.mode === "walkthrough" ? " · ILLUSTRATIVE" : ""}
      </span>
      {Object.entries(outcome.outcomes).map(([name, value]) => (
        <div className="test-item" key={name}>
          {value === "passed" ? (
            <Check size={14} className="text-success" />
          ) : (
            <X size={14} className="text-error" />
          )}
          <span>
            {name.split("::").pop()}
            <small>{name.split("::")[0]}</small>
          </span>
          <span className={value === "passed" ? "text-success" : "text-error"}>
            {value}
          </span>
        </div>
      ))}
      <div className="test-integrity">
        <ShieldCheck size={15} />
        <span>Test files protected · Fresh sandbox for every run</span>
      </div>
      {outcome.infrastructure_error && (
        <div className="inline-error">{outcome.infrastructure_error}</div>
      )}
      <CompareAttempts attempts={run.attempts} />
      <pre className="test-output">{outcome.output_tail}</pre>
    </div>
  );
}
export default function LiveRun() {
  const { id = "" } = useParams();
  const query = useQueryClient();
  const sample = useUI((s) => s.samples.find((r) => r.id === id));
  const updateSample = useUI((s) => s.updateSample);
  const health = useHealth();
  const apiUrl = useUI((s) => s.apiUrl);
  const revision = useUI((s) => s.connectionRevision);
  const connection = { url: apiUrl, token: getToken() };
  const runPath = `/runs/${encodeURIComponent(id)}`;
  const [tab, setTab] = useState("logs");
  const [reconnecting, setReconnecting] = useState(false);
  const [mobile, setMobile] = useState("output");
  const [action, setAction] = useState<"approve" | "reject" | "cancel" | null>(
    null,
  );
  const [, refresh] = useState(0);
  const timelineRef = useRef<HTMLDivElement>(null);
  const live = useQuery({
    queryKey: ["run", apiUrl, revision, id],
    queryFn: ({ signal }) => api<Run>(runPath, { signal }, connection),
    enabled:
      !/^(sample-|recording-)/.test(id) &&
      !!health.data?.database &&
      !!connection.token,
    refetchInterval: 3000,
  });
  const run = sample ?? live.data;
  useEffect(() => {
    const timeline = timelineRef.current;
    const activeStep = timeline?.querySelector(".step-active");
    if (timeline && activeStep) {
      const bottom = activeStep.getBoundingClientRect().bottom;
      const visibleBottom = timeline.getBoundingClientRect().bottom;
      if (bottom > visibleBottom)
        timeline.scrollTop += bottom - visibleBottom + 16;
    }
  }, [run?.events.length, run?.status]);

  useEffect(() => {
    setAction(null);
    setTab("logs");
    setReconnecting(false);
  }, [id, apiUrl, revision]);
  useEffect(() => {
    if (run?.status === "ready_for_review") {
      setTab("diff");
      setMobile("output");
    }
  }, [id, apiUrl, revision, run?.status]);
  useEffect(() => {
    const timer = setInterval(() => refresh((x) => x + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (
      !run ||
      run.mode !== "live" ||
      !["queued", "running", "publishing"].includes(run.status)
    )
      return;
    const controller = new AbortController();
    void followEvents(`${normalizeWorkerUrl(apiUrl)}/api${runPath}/events`, {
      token: connection.token,
      signal: controller.signal,
      onReconnect: setReconnecting,
      onEvent: () => {
        void query.invalidateQueries({
          queryKey: ["run", apiUrl, revision, id],
        });
      },
    });
    return () => controller.abort();
  }, [id, apiUrl, revision, run?.mode, run?.status, !!run]);
  const mutation = useMutation({
    mutationFn: async (kind: "approve" | "reject" | "cancel") => {
      if (!run) return;
      if (run.mode !== "live") {
        updateSample(run.id, {
          status:
            kind === "approve"
              ? "completed"
              : kind === "reject"
                ? "rejected"
                : "cancelled",
          finished_at: new Date().toISOString(),
          reason:
            kind === "approve"
              ? "Playback approved. No PR created."
              : "Playback stopped.",
        });
        return;
      }
      return api(
        `${runPath}/${kind}`,
        {
          method: "POST",
          body: JSON.stringify(
            kind === "approve"
              ? { diff_sha256: await diffHash(run.final_diff) }
              : {},
          ),
        },
        connection,
      );
    },
    onSuccess: () => {
      setAction(null);
      query.invalidateQueries({ queryKey: ["run", apiUrl, revision, id] });
      query.invalidateQueries({ queryKey: ["runs"] });
      toast.success("Decision recorded");
    },
    onError: (e) => toast.error(e.message),
  });
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (
        action ||
        document.querySelector('[role="dialog"]') ||
        e.altKey ||
        (e.target instanceof HTMLElement &&
          (e.target.matches("input,textarea,select") ||
            e.target.isContentEditable))
      )
        return;
      if (
        run?.status === "ready_for_review" &&
        !(run.mode === "live" && live.error) &&
        !e.metaKey &&
        !e.ctrlKey
      ) {
        if (e.key.toLowerCase() === "a") setAction("approve");
        if (e.key.toLowerCase() === "r") setAction("reject");
      }
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [run?.status, action, live.error]);
  if (!run)
    return (
      <div className="page">
        {live.isLoading ||
        (!/^(sample-|recording-)/.test(id) && health.isLoading) ? (
          <>
            <div className="skeleton skeleton-heading" />
            <div className="skeleton skeleton-card" />
          </>
        ) : (
          <div className="empty-state">
            <GitBranch size={30} />
            <h1>Run unavailable</h1>
            <p>
              {/^(sample-|recording-)/.test(id)
                ? "Playback not found in this browser. Start a new example."
                : (live.error?.message ??
                  "Connect the worker that owns this run.")}
            </p>
            <Link className="button button-secondary" to="/workspace">
              Overview
              <ArrowRight size={15} />
            </Link>
          </div>
        )}
      </div>
    );
  const last = run.events.at(-1);
  const active = [...run.events]
    .reverse()
    .find((e) => e.type === "start")?.node;
  const done = new Set(
    run.events
      .filter(
        (e) => e.type === "end" && STEPS.some((step) => step.id === e.node),
      )
      .map((e) => e.node),
  );
  if (["completed", "pr_created"].includes(run.status)) done.add("approval");
  const reviewReady = run.status === "ready_for_review";
  const running = run.status === "running" || run.status === "queued";
  const sampleMode = run.mode !== "live";
  function saveDiff() {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
      new Blob([run!.final_diff], { type: "text/plain" }),
    );
    a.download = `devpilot-${id}.diff`;
    a.click();
    URL.revokeObjectURL(a.href);
  }
  async function saveReport() {
    try {
      const report =
        run!.mode === "live"
          ? await api(`${runPath}/report`, undefined, connection)
          : { schema_version: 1, ...run, recording: undefined };
      const a = document.createElement("a");
      a.href = URL.createObjectURL(
        new Blob([JSON.stringify(report, null, 2)], {
          type: "application/json",
        }),
      );
      a.download = `devpilot-${id}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      toast.success("Run report downloaded");
    } catch (e) {
      toast.error(
        e instanceof Error
          ? e.message
          : "Reconnect and retry the report download.",
      );
    }
  }
  return (
    <div className="page live-page">
      {run.mode === "live" && live.error && (
        <div className="connection-banner" role="status">
          Updates paused. Check your worker connection.
        </div>
      )}
      <div className="live-heading">
        <div>
          <Link className="back-link" to="/runs">
            <ArrowLeft size={13} />
            Run history
          </Link>
          <h1>
            <Github size={23} />
            {formatRepo(run.repo_url)}
            <StatusBadge status={activityStatus(run, reconnecting)} />
          </h1>
          <p>{run.issue_text}</p>
        </div>
        <div className="live-heading-actions">
          <Button variant="secondary" size="sm" onClick={saveReport}>
            <ArrowDownToLine size={16} />
            Report
          </Button>
          {!sampleMode && (
            <button
              className="icon-control"
              title="Copy run URL"
              aria-label="Copy run URL"
              onClick={() => copy(location.href)}
            >
              <Copy size={16} />
            </button>
          )}
          {running && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setAction("cancel")}
            >
              <Square size={12} />
              Stop run
            </Button>
          )}
        </div>
      </div>
      {sampleMode && (
        <div className="sample-banner">
          <Info size={15} />
          <span>
            {run.mode === "replay" ? (
              <>
                <strong>Recorded real run.</strong>{" "}
                {run.recorded_at
                  ? new Date(run.recorded_at).toLocaleDateString()
                  : ""}{" "}
                · Playback only.
              </>
            ) : (
              <>
                <strong>Illustrative sample.</strong> No live services.
              </>
            )}
          </span>
          <div>
            <button
              aria-label={
                run.paused ? "Resume walkthrough" : "Pause walkthrough"
              }
              onClick={() => updateSample(id, { paused: !run.paused })}
            >
              {run.paused ? <Play size={14} /> : <Pause size={14} />}
            </button>
            <button
              onClick={() => {
                const fresh =
                  run.mode === "replay" && run.recording
                    ? makeRecorded(run.recording)
                    : makeSample(run.example ?? "slugify");
                updateSample(id, {
                  ...fresh,
                  id,
                  created_at: new Date().toISOString(),
                });
              }}
            >
              <RotateCcw size={13} />
              <span>Replay</span>
            </button>
          </div>
        </div>
      )}
      <FailureExplanation
        run={run}
        onTests={() => {
          setTab("tests");
          setMobile("output");
        }}
      />
      <div className="mobile-run-tabs">
        {["timeline", "output"].map((t) => (
          <button
            key={t}
            className={mobile === t ? "active" : ""}
            onClick={() => setMobile(t)}
          >
            {t === "output" ? "Workspace" : t[0].toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      <div className="live-grid">
        <aside
          className={`panel timeline-panel mobile-panel-${mobile === "timeline" ? "visible" : "hidden"}`}
        >
          <div className="panel-header">
            <span>
              <GitBranch size={15} />
              Progress
            </span>
            <span className="muted mono">
              {done.size}/{STEPS.length}
            </span>
          </div>
          <div className="timeline" ref={timelineRef}>
            {STEPS.map((step, i) => {
              const complete =
                done.has(step.id) ||
                (step.id === "approval" &&
                  ["completed", "pr_created"].includes(run.status));
              const isActive =
                !complete &&
                (active === step.id || (step.id === "approval" && reviewReady));
              const failed = run.status === "failed" && active === step.id;
              return (
                <div
                  key={step.id}
                  className={`timeline-step ${complete ? "step-done" : isActive ? "step-active" : ""} ${failed ? "step-failed" : ""}`}
                >
                  <span className="timeline-step-icon">
                    {complete ? (
                      <Check size={13} />
                    ) : failed ? (
                      <X size={13} />
                    ) : isActive ? (
                      <span />
                    ) : (
                      <small>{String(i + 1).padStart(2, "0")}</small>
                    )}
                  </span>
                  <div>
                    <strong>{step.label}</strong>
                    {isActive && <p>{step.detail}</p>}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="timeline-footer">
            <LockKeyhole size={14} />
            No target push before approval
          </div>
        </aside>
        <section
          className={`panel output-panel mobile-panel-${mobile === "output" ? "visible" : "hidden"}`}
        >
          <div
            className="output-tabs"
            role="tablist"
            aria-label="Workspace"
            onKeyDown={(event) => {
              if (
                !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)
              )
                return;
              event.preventDefault();
              const tabs = [
                ...event.currentTarget.querySelectorAll<HTMLButtonElement>(
                  '[role="tab"]',
                ),
              ];
              const index = tabs.indexOf(
                document.activeElement as HTMLButtonElement,
              );
              const next =
                event.key === "Home"
                  ? 0
                  : event.key === "End"
                    ? tabs.length - 1
                    : (index +
                        (event.key === "ArrowRight" ? 1 : -1) +
                        tabs.length) %
                      tabs.length;
              tabs[next]?.focus();
              tabs[next]?.click();
            }}
          >
            {[
              { id: "logs", icon: Terminal, label: "Activity" },
              { id: "diff", icon: Code2, label: "Diff" },
              { id: "tests", icon: FlaskConical, label: "Tests" },
              { id: "summary", icon: BookOpen, label: "Review" },
              { id: "workflow", icon: GitBranch, label: "Workflow" },
            ].map(({ id: tabId, icon: Icon, label }) => (
              <button
                role="tab"
                tabIndex={tab === tabId ? 0 : -1}
                aria-selected={tab === tabId}
                id={`tab-${tabId}`}
                aria-controls="output-tabpanel"
                className={tab === tabId ? "active" : ""}
                onClick={() => setTab(tabId)}
                key={tabId}
              >
                <Icon size={13} />
                {label}
                {tabId === "diff" && run.final_diff && (
                  <span className="tab-dot" />
                )}
              </button>
            ))}
          </div>
          <div className="output-toolbar">
            <span>
              {tab === "logs" ? (
                <>
                  <span
                    className={`status-dot ${running ? "green" : "violet"}`}
                  />
                  {sampleMode
                    ? "Playback"
                    : running
                      ? "Live activity"
                      : "Activity"}
                  <span className="muted">· {run.events.length} events</span>
                </>
              ) : tab === "diff" ? (
                "UNIFIED DIFF"
              ) : tab === "tests" ? (
                "PYTEST RESULTS"
              ) : tab === "workflow" ? (
                "WORKFLOW"
              ) : (
                "REVIEW"
              )}
            </span>
            <button
              aria-label={`Copy ${tab}`}
              className="icon-control"
              disabled={tab === "workflow"}
              onClick={() =>
                copy(
                  tab === "diff"
                    ? run.final_diff
                    : tab === "logs"
                      ? run.events
                          .map((e) => `${e.node}: ${e.message}`)
                          .join("\n")
                      : tab === "summary"
                        ? run.review
                        : JSON.stringify(
                            run.attempts.at(-1)?.test_result ??
                              run.baseline_result,
                            null,
                            2,
                          ),
                )
              }
            >
              <Copy size={13} />
            </button>
          </div>
          <div
            role="tabpanel"
            id="output-tabpanel"
            aria-labelledby={`tab-${tab}`}
            className="output-content"
          >
            {tab === "logs" ? (
              <>
                {run.relevant_files.length > 0 && (
                  <div className="context-files">
                    {run.relevant_files.join(", ")}
                  </div>
                )}
                <Logs events={run.events} />
              </>
            ) : tab === "workflow" ? (
              <div className="workflow-drawer">
                <Suspense fallback={<div className="skeleton skeleton-card" />}>
                  <AgentGraph run={run} />
                </Suspense>
              </div>
            ) : tab === "diff" ? (
              <div
                className={`diff-workspace ${reviewReady ? "with-review" : ""}`}
              >
                <Diff diff={run.final_diff} />
                {reviewReady && (
                  <aside className="review-evidence">
                    <h2>Review the patch</h2>
                    <p>{run.review}</p>
                    <h3>Test evidence</h3>
                    <p>
                      {
                        Object.keys(
                          run.attempts.at(-1)?.test_result?.outcomes ?? {},
                        ).length
                      }{" "}
                      tests recorded · exit{" "}
                      {run.attempts.at(-1)?.test_result?.exit_code ?? "—"}
                    </p>
                    <div className="risk-note">
                      <Info size={16} />
                      <span>
                        Review behavior and edge cases before approving.
                      </span>
                    </div>
                  </aside>
                )}
              </div>
            ) : tab === "tests" ? (
              <Tests run={run} />
            ) : run.review ? (
              <div className="summary-tab">
                <span className="summary-icon">
                  <ShieldCheck size={21} />
                </span>
                <h2>Review</h2>
                <ReviewChecklist run={run} />
                <p className="review-prose">{run.review}</p>
              </div>
            ) : (
              <div className="tab-empty">
                <BookOpen size={27} />
                <strong>Review pending</strong>
                <p>Available after tests pass.</p>
              </div>
            )}
          </div>
        </section>
      </div>
      <div className={`run-bottom-bar ${reviewReady ? "approval-ready" : ""}`}>
        <div className="run-bottom-info">
          <span>
            <span
              className={`status-dot ${reviewReady ? "amber" : running ? "green" : "violet"}`}
            />
            {reviewReady
              ? "Your review is the next step"
              : running
                ? last?.node === "baseline"
                  ? "Reproducing the failure"
                  : "Agent is working"
                : run.reason || "Run finished"}
          </span>
          <div>
            <span>
              Attempt <strong>{run.attempts.length || "—"} / 3</strong>
            </span>
            <span>
              <Clock3 size={13} />
              <strong>{elapsed(run.created_at, run.finished_at)}</strong>
            </span>
            <span className="dry-run-label">
              <ShieldCheck size={13} />
              {run.dry_run ? "Dry run" : "Approval required"}
            </span>
          </div>
        </div>
        <div className="approval-actions">
          {run.final_diff && (
            <Button
              variant="ghost"
              size="sm"
              onClick={saveDiff}
              title="Download patch"
            >
              <ArrowDownToLine size={15} />
              <span className="download-label">Diff</span>
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            disabled={
              !reviewReady ||
              mutation.isPending ||
              (run.mode === "live" && !!live.error)
            }
            onClick={() => setAction("reject")}
          >
            <X size={14} />
            Reject<kbd>R</kbd>
          </Button>
          <Button
            size="sm"
            disabled={
              !reviewReady ||
              mutation.isPending ||
              (run.mode === "live" && !!live.error)
            }
            onClick={() => setAction("approve")}
          >
            <Check size={15} />
            {sampleMode || run.dry_run
              ? "Approve patch"
              : "Approve and open draft PR"}
            <kbd>A</kbd>
          </Button>
        </div>
      </div>
      {run.pr_url && (
        <a
          className="pr-success"
          href={run.pr_url}
          target="_blank"
          rel="noreferrer"
        >
          <GitPullRequest size={19} />
          <span>Your pull request is ready to review.</span>Open PR
          <ExternalLink size={14} />
        </a>
      )}
      <Dialog
        open={!!action}
        onOpenChange={(v) => !v && setAction(null)}
        title={
          action === "approve"
            ? sampleMode
              ? "Finish this playback?"
              : run.dry_run
                ? "Approve this dry-run patch?"
                : "Approve and open a draft PR?"
            : action === "reject"
              ? "Reject this patch?"
              : "Stop this run?"
        }
        description={
          action === "approve"
            ? sampleMode
              ? "Saved in this browser only. No PR is created."
              : run.dry_run
                ? "Approve this exact diff. No target branch or PR will be created."
                : "Push the reviewed patch to a new target branch and open a draft PR. Nothing is merged."
            : action === "reject"
              ? "Keep the patch in history without publishing it."
              : "The worker will stop at its next cancellation check and remove its sandbox."
        }
      >
        <div className="approval-dialog-detail">
          <ShieldCheck size={20} />
          <div>
            <strong>{formatRepo(run.repo_url)}</strong>
            <p>
              {run.attempts.length} attempt ·{" "}
              {run.final_diff ? "Validated diff" : "Investigation in progress"}{" "}
              ·{" "}
              {sampleMode
                ? "Scripted sample"
                : run.dry_run
                  ? "Dry run"
                  : "Live run"}
            </p>
          </div>
        </div>
        <div className="dialog-footer">
          <Button variant="secondary" onClick={() => setAction(null)}>
            Go back
          </Button>
          <Button
            variant={
              action === "reject" || action === "cancel" ? "danger" : "default"
            }
            disabled={mutation.isPending}
            onClick={() => action && mutation.mutate(action)}
          >
            {mutation.isPending ? (
              <LoaderCircle size={15} className="spin" />
            ) : action === "approve" ? (
              <Check size={15} />
            ) : (
              <X size={15} />
            )}
            Confirm{" "}
            {action === "approve"
              ? "approval"
              : action === "reject"
                ? "rejection"
                : "stop"}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}
