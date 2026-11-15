import { Check, Info } from "lucide-react";
import type { Run } from "../lib/types";
export function failureNextStep(run: Run): string {
  if (/rate limit|throttl/i.test(run.reason))
    return "Wait for the provider budget to reset, then start a new run.";
  if (run.status === "unsuitable")
    return "Resolve the test setup or unrelated failures, or choose another repository.";
  if (run.status === "timeout")
    return "Choose a smaller test suite or repository, then start a new run.";
  return "Inspect the test evidence and readiness check, then retry with a clearer reproduction.";
}
export function FailureExplanation({
  run,
  onTests,
}: {
  run: Run;
  onTests: () => void;
}) {
  if (!["failed", "timeout", "unsuitable"].includes(run.status)) return null;
  return (
    <section className="failure-card" role="alert">
      <h2>Investigation stopped</h2>
      <dl>
        <dt>What failed</dt>
        <dd>
          {run.reason ||
            "The worker stopped before a reviewed patch was ready."}
        </dd>
        <dt>What was tried</dt>
        <dd>
          {run.attempts.length} patch attempt
          {run.attempts.length === 1 ? "" : "s"}.{" "}
          {run.baseline_result
            ? `${Object.keys(run.baseline_result.outcomes).length} baseline test outcomes recorded.`
            : "No baseline test evidence was recorded."}
        </dd>
        <dt>Next step</dt>
        <dd>{failureNextStep(run)}</dd>
      </dl>
      <button className="button button-secondary" onClick={onTests}>
        Inspect tests
      </button>
    </section>
  );
}
export function ReviewChecklist({ run }: { run: Run }) {
  const paths = [...run.final_diff.matchAll(/^\+\+\+ b\/(.+)$/gm)].map(
    (m) => m[1],
  );
  const protectedFiles =
    paths.length > 0 &&
    paths.length <= 5 &&
    paths.every(
      (p) =>
        p.endsWith(".py") &&
        !p
          .split("/")
          .some(
            (x) => x.startsWith(".") || x.toLowerCase().startsWith("test"),
          ) &&
        !/(^|\/)(conftest|setup|noxfile|fabfile)\.py$/.test(p) &&
        !p.endsWith("_test.py"),
    );
  const result = run.attempts.at(-1)?.test_result;
  const tested =
    !!result &&
    result.exit_code === 0 &&
    !result.infrastructure_error &&
    !result.timed_out &&
    Object.keys(result.outcomes).length > 0 &&
    Object.values(result.outcomes).every((x) =>
      ["passed", "skipped", "xfailed"].includes(x),
    );
  return (
    <section className="review-checklist">
      <h3>Review checklist</h3>
      <ul>
        <li>
          <Check size={16} />
          <span>
            <strong>Scope of change</strong>
            {paths.length ? paths.join(", ") : "No validated diff yet"}
          </span>
        </li>
        <li>
          <span>{tested ? <Check size={16} /> : <Info size={16} />}</span>
          <span>
            <strong>Test evidence</strong>
            {tested
              ? `${Object.keys(result!.outcomes).length} outcomes · exit 0`
              : "Passing final test evidence is not available"}
          </span>
        </li>
        <li>
          {protectedFiles ? <Check size={16} /> : <Info size={16} />}
          <span>
            <strong>Protected files</strong>
            {protectedFiles
              ? "Diff contains source files only; tests are untouched."
              : "Inspect patch scope before approval."}
          </span>
        </li>
        <li>
          <Info size={16} />
          <span>
            <strong>Remaining risks</strong>Review edge cases, behavior and the
            explanation. Tests cannot prove the fix is correct.
          </span>
        </li>
      </ul>
    </section>
  );
}
