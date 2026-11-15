import type { Run, RunEvent, TestResult } from "./types";
export function makeRecorded(record: Run): Run {
  if (!record.test_evidence?.length)
    throw new Error("Recording has no remote test evidence.");
  return {
    ...record,
    id: `recording-${record.id}-${crypto.randomUUID().slice(0, 8)}`,
    source_run_id: record.id,
    recording: record,
    mode: "replay",
    status: "running",
    created_at: new Date().toISOString(),
    finished_at: null,
    cursor: 0,
    events: [],
    attempts: [],
    final_diff: "",
    review: "",
    hypothesis: "",
    baseline_result: null,
    dry_run: true,
    paused: false,
    speed: 10,
    playback_elapsed: 0,
    playback_tick: Date.now(),
  };
}
function applyEvent(run: Run, event: RunEvent): Run {
  const p = event.payload ?? {};
  const next = { ...run, events: [...run.events, event] };
  if (typeof p.hypothesis === "string") next.hypothesis = p.hypothesis;
  if (p.baseline_result) next.baseline_result = p.baseline_result as TestResult;
  if (Array.isArray(p.relevant_files))
    next.relevant_files = p.relevant_files as string[];
  if (
    event.node === "patch" &&
    event.type === "end" &&
    typeof p.attempts === "number"
  )
    next.attempts = [...run.attempts, { attempt_no: p.attempts, patch: "" }];
  if (
    event.node === "validate_patch" &&
    !p.feedback &&
    typeof p.patch === "string" &&
    p.patch.startsWith("--- a/")
  ) {
    next.final_diff = p.patch;
    next.attempts = next.attempts.map((a, i) =>
      i === next.attempts.length - 1 ? { ...a, patch: p.patch as string } : a,
    );
  }
  if (p.test_result)
    next.attempts = next.attempts.map((a, i) =>
      i === next.attempts.length - 1
        ? { ...a, test_result: p.test_result as TestResult }
        : a,
    );
  return next;
}
export function advanceRecorded(run: Run, now = Date.now()): Run {
  if (run.mode !== "replay" || run.status !== "running" || !run.recording)
    return run;
  if (run.paused) return { ...run, playback_tick: now };
  const elapsed =
    (run.playback_elapsed ?? 0) +
    Math.max(0, now - (run.playback_tick ?? now)) * (run.speed ?? 10);
  const events = run.recording.events;
  const first = new Date(
    events[0]?.timestamp ?? run.recording.created_at,
  ).getTime();
  let next: Run = { ...run, playback_elapsed: elapsed, playback_tick: now };
  let cursor = run.cursor ?? 0;
  while (
    cursor < events.length &&
    new Date(events[cursor].timestamp).getTime() - first <= elapsed
  )
    next = applyEvent(next, events[cursor++]);
  if (cursor === events.length)
    next = {
      ...next,
      status: "ready_for_review",
      final_diff: run.recording.final_diff,
      attempts: run.recording.attempts,
      review: run.recording.review,
      hypothesis: run.recording.hypothesis,
      baseline_result: run.recording.baseline_result,
      relevant_files: run.recording.relevant_files,
      finished_at: new Date(now).toISOString(),
    };
  return { ...next, cursor };
}
