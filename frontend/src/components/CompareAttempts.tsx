import { lazy, Suspense, useState } from "react";
import type { Attempt } from "../lib/types";
const PatchViewer = lazy(() => import("./PatchViewer"));
function failures(attempt: Attempt) {
  return Object.entries(attempt.test_result?.outcomes ?? {})
    .filter(([, v]) => !["passed", "skipped", "xfailed"].includes(v))
    .map(([name]) => name);
}
export function CompareAttempts({ attempts }: { attempts: Attempt[] }) {
  const [earlier, setEarlier] = useState(0);
  const [later, setLater] = useState<number | null>(null);
  if (attempts.length < 2) return null;
  const left = attempts[earlier] ?? attempts[0],
    right = attempts[later ?? attempts.length - 1] ?? attempts.at(-1)!;
  const remaining = failures(right),
    resolved = failures(left).filter((name) => !remaining.includes(name));
  return (
    <details className="attempt-comparison">
      <summary>Compare attempts</summary>
      <div className="attempt-selectors">
        <label>
          Earlier attempt
          <select
            value={earlier}
            onChange={(e) => setEarlier(Number(e.target.value))}
          >
            {attempts.map((a, i) => (
              <option key={a.attempt_no} value={i}>
                Attempt {a.attempt_no}
              </option>
            ))}
          </select>
        </label>
        <label>
          Later attempt
          <select
            value={later ?? attempts.length - 1}
            onChange={(e) => setLater(Number(e.target.value))}
          >
            {attempts.map((a, i) => (
              <option key={a.attempt_no} value={i}>
                Attempt {a.attempt_no}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p>
        Resolved test failures:{" "}
        {resolved.length ? resolved.join(", ") : "None recorded"}
      </p>
      <p>
        Still failing:{" "}
        {remaining.length
          ? remaining.join(", ")
          : "None recorded. Inspect setup errors and test inventory too."}
      </p>
      <div className="attempt-patches">
        {[left, right].map((a, i) => (
          <section key={i}>
            <h4>Attempt {a.attempt_no}</h4>
            {a.validation_error && (
              <p className="text-error">{a.validation_error}</p>
            )}
            <Suspense fallback={<div className="skeleton skeleton-card" />}>
              {a.patch.startsWith("--- a/") ? (
                <PatchViewer diff={a.patch} />
              ) : (
                <pre>{a.patch || "No patch recorded"}</pre>
              )}
            </Suspense>
          </section>
        ))}
      </div>
    </details>
  );
}
