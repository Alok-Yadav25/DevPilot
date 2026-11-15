import type { Run, RunEvent } from "./types";
export const EXAMPLES = [
  {
    id: "slugify",
    name: "The wrong separator",
    repo: "slugify",
    category: "String handling",
    description:
      "A slug helper turns “Hello World” into hello_world. It should return hello-world.",
    file: "slugify.py",
    test: "test_separator",
    testCount: 2,
    old: 'return "_".join(text.strip().lower().split())',
    fix: 'return "-".join(text.strip().lower().split())',
    hypothesis:
      "The slug helper joins normalized words with an underscore. Replacing the separator with a hyphen fixes the failing case while preserving whitespace normalization.",
    icon: "text",
  },
  {
    id: "clamp",
    name: "A boundary mix-up",
    repo: "clamp",
    category: "Edge cases",
    description:
      "Values inside the range are clamped to the lower bound. Find the reversed min/max logic.",
    file: "clamp.py",
    test: "test_bounds",
    testCount: 2,
    old: "return min(lower, max(upper, value))",
    fix: "return max(lower, min(upper, value))",
    hypothesis:
      "The min and max calls use reversed bounds. First limit the value to the upper bound, then enforce the lower bound.",
    icon: "bounds",
  },
  {
    id: "backoff",
    name: "One attempt ahead",
    repo: "backoff",
    category: "Off-by-one",
    description:
      "The first retry waits twice as long as expected. Trace an off-by-one error in exponential backoff.",
    file: "backoff.py",
    test: "test_first_delay",
    testCount: 3,
    old: "return min(cap, 2 ** (attempt + 1))",
    fix: "return min(cap, 2 ** attempt)",
    hypothesis:
      "Incrementing the exponent makes attempt zero return two. Using the original attempt index starts delays at one while preserving the cap.",
    icon: "clock",
  },
];
export function sampleDiff(id: string) {
  const e = EXAMPLES.find((e) => e.id === id) ?? EXAMPLES[0];
  return `--- a/${e.file}\n+++ b/${e.file}\n@@ -4,2 +4,2 @@\n def ${e.id}(${e.id === "slugify" ? "text: str" : e.id === "clamp" ? "value: int, lower: int, upper: int" : "attempt: int, cap: int = 32"}):\n-    ${e.old}\n+    ${e.fix}\n`;
}
export function sampleEvents(id: string, start: string): RunEvent[] {
  const e = EXAMPLES.find((e) => e.id === id) ?? EXAMPLES[0];
  const rows: [string, RunEvent["type"], string][] = [
    ["clone", "start", "Preparing a clean repository workspace…"],
    ["clone", "end", `Loaded the local ${e.repo} fixture. 4 files checked.`],
    ["baseline", "start", "Running pytest in a fresh, networkless sandbox…"],
    [
      "baseline",
      "waiting",
      `Baseline 1/2: ${e.test} fails with AssertionError.`,
    ],
    ["baseline", "end", "Baseline 2/2 matches. The failure is reproducible."],
    ["locate", "start", "Tracing the failure to production source…"],
    [
      "locate",
      "end",
      `Selected ${e.file} and its regression test for context.`,
    ],
    ["diagnose", "start", "Comparing the issue with the failing assertion…"],
    ["diagnose", "end", e.hypothesis],
    ["patch", "start", "Generating a focused search/replace patch…"],
    ["patch", "end", "Candidate ready. 1 source file, 1 line replaced."],
    ["validate_patch", "start", "Checking patch scope and protected paths…"],
    ["validate_patch", "end", "Diff applies cleanly. No test files changed."],
    ["test", "start", "Running the complete pytest suite in a new sandbox…"],
    [
      "test",
      "end",
      `Illustrative outcome: ${e.testCount} passed, 0 failed. Test inventory preserved.`,
    ],
    ["review", "start", "Preparing an explanation and risk review…"],
    [
      "review",
      "end",
      "Review ready. Your approval is required before a live run could publish.",
    ],
    [
      "approval",
      "start",
      "Waiting for your review. No branch has been pushed.",
    ],
  ];
  return rows.map(([node, type, message], i) => ({
    id: i + 1,
    node,
    type,
    message,
    timestamp: new Date(new Date(start).getTime() + i * 1600).toISOString(),
  }));
}
export function makeSample(id: string): Run {
  const e = EXAMPLES.find((e) => e.id === id) ?? EXAMPLES[0];
  return {
    id: `sample-${crypto.randomUUID().slice(0, 8)}`,
    repo_url: `examples/${e.repo}`,
    issue_text: e.description,
    status: "running",
    reason:
      "Interactive walkthrough — scripted data, no repository or API accessed.",
    created_at: new Date().toISOString(),
    attempts: [],
    events: [],
    final_diff: "",
    review: "",
    hypothesis: "",
    relevant_files: [],
    dry_run: true,
    mode: "walkthrough",
    example: id,
    cursor: 0,
    paused: false,
    speed: 1,
  };
}
export function advanceSample(run: Run): Run {
  if (run.status !== "running" || run.paused) return run;
  const all = sampleEvents(run.example ?? "slugify", run.created_at);
  const cursor = Math.min((run.cursor ?? 0) + 1, all.length);
  const events = all.slice(0, cursor);
  const e = EXAMPLES.find((e) => e.id === run.example) ?? EXAMPLES[0];
  const at = (node: string) =>
    events.some((x) => x.node === node && x.type === "end");
  const test = {
    exit_code: 0,
    outcomes: Object.fromEntries(
      Array.from({ length: e.testCount }, (_, i) => [
        `tests/test_${e.id}.py::${i === 0 ? e.test : `test_case_${i}`}`,
        "passed",
      ]),
    ),
    output_tail: `${e.testCount} passed in 0.04s (illustrative sample output)`,
    duration_seconds: 0.04,
  };
  return {
    ...run,
    cursor,
    events,
    status: cursor === all.length ? "ready_for_review" : "running",
    hypothesis: at("diagnose") ? e.hypothesis : "",
    relevant_files: at("locate") ? [e.file, `tests/test_${e.id}.py`] : [],
    final_diff: at("validate_patch") ? sampleDiff(e.id) : "",
    attempts: at("patch")
      ? [
          {
            attempt_no: 1,
            patch: sampleDiff(e.id),
            test_result: at("test") ? test : undefined,
          },
        ]
      : [],
    baseline_result: at("baseline")
      ? {
          ...test,
          exit_code: 1,
          outcomes: {
            ...test.outcomes,
            [`tests/test_${e.id}.py::${e.test}`]: "failed",
          },
        }
      : undefined,
    review: at("review")
      ? `Changes the expression in ${e.file} to address the reported behavior. The illustrated suite preserves its test inventory.\n\nRisks: these small synthetic cases cover only a few inputs. Review requirements and edge cases before applying a real patch. Passing tests do not prove correctness.\n\nThis walkthrough uses scripted events and expected outcomes. It is not evidence of an autonomous repair.`
      : "",
  };
}
