import {
  Check,
  Circle,
  LoaderCircle,
  X,
  CirclePause,
  GitPullRequest,
} from "lucide-react";
import type { Run, RunStatus } from "../lib/types";
type ActivityStatus =
  | RunStatus
  | "waiting_for_runner"
  | "testing"
  | "rate_limited"
  | "reconnecting";
export function activityStatus(run: Run, reconnecting = false): ActivityStatus {
  if (reconnecting) return "reconnecting";
  if (run.status !== "running") return run.status;
  const last = run.events.at(-1);
  if (last?.type === "waiting" && /rate limit/i.test(last.message))
    return "rate_limited";
  if (last?.node === "sandbox" && last.type === "waiting")
    return "waiting_for_runner";
  if (last && ["test", "baseline"].includes(last.node) && last.type !== "end")
    return "testing";
  return run.status;
}
const labels: Record<ActivityStatus, string> = {
  waiting_for_runner: "Waiting for GitHub runner",
  testing: "Testing",
  rate_limited: "Rate limited · waiting",
  reconnecting: "Reconnecting",
  queued: "Queued",
  running: "In progress",
  ready_for_review: "Waiting for approval",
  completed: "Approved",
  pr_created: "PR opened",
  rejected: "Rejected",
  unsuitable: "Unsuitable",
  failed: "Failed",
  cancelled: "Cancelled",
  timeout: "Timed out",
  publishing: "Opening PR",
};
export function StatusBadge({ status }: { status: ActivityStatus }) {
  const done = ["completed", "pr_created"].includes(status);
  const fail = ["failed", "timeout", "rejected", "unsuitable"].includes(status);
  const active = [
    "running",
    "publishing",
    "waiting_for_runner",
    "testing",
    "rate_limited",
    "reconnecting",
  ].includes(status);
  const Icon =
    status === "pr_created"
      ? GitPullRequest
      : done
        ? Check
        : fail
          ? X
          : active
            ? LoaderCircle
            : status === "ready_for_review"
              ? CirclePause
              : Circle;
  return (
    <span
      role="status"
      aria-live="polite"
      className={`status-badge ${done ? "status-success" : fail ? "status-error" : active ? "status-progress" : status === "ready_for_review" ? "status-review" : "status-muted"}`}
    >
      <Icon size={12} className={active ? "spin" : ""} />
      {labels[status]}
    </span>
  );
}
