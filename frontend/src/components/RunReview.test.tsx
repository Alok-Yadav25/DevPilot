import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FailureExplanation, ReviewChecklist } from "./RunReview";
import { CompareAttempts } from "./CompareAttempts";
import { advanceSample, makeSample } from "../lib/examples";
function ready() {
  let run = makeSample("slugify");
  for (let i = 0; i < 20; i++) run = advanceSample(run);
  return run;
}
describe("review evidence and next steps", () => {
  it("shows specific recovery guidance for rate limits", () => {
    const run = {
      ...ready(),
      status: "failed" as const,
      reason: "Groq rate limit exceeded",
    };
    render(<FailureExplanation run={run} onTests={() => {}} />);
    expect(screen.getByText(/Wait for the provider budget/)).not.toBeNull();
    expect(screen.getByText(/patch attempt/)).not.toBeNull();
  });
  it("does not mark a test-file patch as protected", () => {
    const run = {
      ...ready(),
      final_diff: "--- a/tests/test_x.py\n+++ b/tests/test_x.py\n",
    };
    render(<ReviewChecklist run={run} />);
    expect(
      screen.getByText("Inspect patch scope before approval."),
    ).not.toBeNull();
  });
  it("compares actual remaining and resolved failures", async () => {
    const run = ready();
    const attempts = [
      {
        attempt_no: 1,
        patch: "{}",
        test_result: {
          exit_code: 1,
          outcomes: { test_a: "failed", test_b: "failed" },
          output_tail: "",
          duration_seconds: 1,
        },
      },
      {
        ...run.attempts[0],
        attempt_no: 2,
        test_result: {
          exit_code: 1,
          outcomes: { test_a: "passed", test_b: "failed" },
          output_tail: "",
          duration_seconds: 1,
        },
      },
    ];
    render(<CompareAttempts attempts={attempts} />);
    await userEvent.click(screen.getByText("Compare attempts"));
    expect(screen.getByText("Resolved test failures: test_a")).not.toBeNull();
    expect(screen.getByText("Still failing: test_b")).not.toBeNull();
  });
});
