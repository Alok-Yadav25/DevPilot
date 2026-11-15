export type RunStatus =
  | "queued"
  | "running"
  | "ready_for_review"
  | "completed"
  | "pr_created"
  | "rejected"
  | "unsuitable"
  | "failed"
  | "cancelled"
  | "timeout"
  | "publishing";
export type TestResult = {
  exit_code: number;
  outcomes: Record<string, string>;
  output_tail: string;
  duration_seconds: number;
  infrastructure_error?: string;
  timed_out?: boolean;
};
export type RunEvent = {
  id?: number;
  timestamp: string;
  node: string;
  type: "start" | "end" | "waiting" | "error";
  message: string;
  payload?: Record<string, unknown>;
};
export type Attempt = {
  attempt_no: number;
  patch: string;
  validation_error?: string;
  test_result?: TestResult | null;
};
export type Run = {
  id: string;
  repo_url: string;
  issue_text: string;
  status: RunStatus;
  reason: string;
  created_at: string;
  finished_at?: string | null;
  attempts: Attempt[];
  events: RunEvent[];
  final_diff: string;
  review: string;
  hypothesis: string;
  relevant_files: string[];
  baseline_result?: TestResult | null;
  pr_url?: string | null;
  commit_sha?: string;
  model?: string;
  approval_record?: {
    approved: boolean;
    diff_sha256?: string;
    events?: RunEvent[];
  };
  approved?: boolean;
  dry_run: boolean;
  mode: "live" | "walkthrough" | "replay";
  recording?: Run;
  recorded_at?: string;
  source_run_id?: string;
  playback_elapsed?: number;
  playback_tick?: number;
  test_evidence?: {
    job_id: string;
    run_id: number;
    status: string;
    url: string;
  }[];
  example?: string;
  cursor?: number;
  paused?: boolean;
  speed?: number;
};
export type Health = {
  status: string;
  database: boolean;
  runner: "github_actions" | "docker" | "replay";
  runner_healthy: boolean;
  runner_error?: string;
  groq_configured: boolean;
  github_configured: boolean;
  ready: boolean;
  model: string;
  message: string;
};
export type Evaluation = {
  total_cases: number;
  executed: number;
  passed: number;
  failed: number;
  success_rate: number | null;
  average_attempts: number | null;
  results: {
    id: string;
    name: string;
    repo: string;
    category: string;
    status: string;
    attempts: number;
    duration_seconds: number | null;
  }[];
};
export const TERMINAL = [
  "completed",
  "pr_created",
  "rejected",
  "unsuitable",
  "failed",
  "cancelled",
  "timeout",
];
export const STEPS = [
  {
    id: "clone",
    label: "Clone repository",
    detail: "A clean, shallow checkout",
  },
  {
    id: "baseline",
    label: "Reproduce the bug",
    detail: "Run the baseline twice",
  },
  {
    id: "locate",
    label: "Locate relevant code",
    detail: "Read traces and source",
  },
  {
    id: "diagnose",
    label: "Form a hypothesis",
    detail: "Understand the root cause",
  },
  {
    id: "patch",
    label: "Generate a patch",
    detail: "Small, focused source edits",
  },
  {
    id: "validate_patch",
    label: "Validate the diff",
    detail: "Protect tests and scope",
  },
  {
    id: "test",
    label: "Run the tests",
    detail: "Selected isolated test runner",
  },
  {
    id: "review",
    label: "Review the change",
    detail: "Explain evidence and risks",
  },
  {
    id: "approval",
    label: "Human approval",
    detail: "You make the final call",
  },
];
