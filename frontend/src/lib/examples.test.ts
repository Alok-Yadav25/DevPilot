import { describe, expect, it } from "vitest";
import { advanceSample, EXAMPLES, makeSample, sampleDiff } from "./examples";
import { parsePatch } from "./diff";
import catalog from "./evaluation-cases.json";
describe("Honest interactive walkthroughs", () => {
  it.each(EXAMPLES)(
    "$id advances through every stage and stops for approval",
    (example) => {
      let run = makeSample(example.id);
      for (let i = 0; i < 30; i++) run = advanceSample(run);
      expect(run.status).toBe("ready_for_review");
      expect(run.mode).toBe("walkthrough");
      expect(run.dry_run).toBe(true);
      expect(run.pr_url).toBeUndefined();
      expect(
        run.events.filter((e) => e.type === "start").map((e) => e.node),
      ).toEqual([
        "clone",
        "baseline",
        "locate",
        "diagnose",
        "patch",
        "validate_patch",
        "test",
        "review",
        "approval",
      ]);
      expect(run.review).toContain("scripted events");
      expect(run.attempts[0].test_result?.exit_code).toBe(0);
    },
  );
  it("pause and cancellation prevent further sample events", () => {
    const run = makeSample("slugify");
    expect(advanceSample({ ...run, paused: true }).events).toHaveLength(0);
    expect(advanceSample({ ...run, status: "cancelled" }).events).toHaveLength(
      0,
    );
  });
  it.each(EXAMPLES)(
    "$id emits a parsable diff with the correct path",
    (example) => {
      const files = parsePatch(sampleDiff(example.id));
      expect(files).toHaveLength(1);
      expect(files[0].newPath).toBe(example.file);
      expect(
        files[0].hunks[0].changes.filter((c) => c.type === "insert"),
      ).toHaveLength(1);
    },
  );
  it("preserves multiple file boundaries in real git-apply patches", () => {
    const files = parsePatch(sampleDiff("slugify") + sampleDiff("clamp"));
    expect(files.map((f) => f.newPath)).toEqual(["slugify.py", "clamp.py"]);
  });
  it("has 25 unique curated cases, never stored as fabricated results", () => {
    expect(catalog).toHaveLength(25);
    expect(new Set(catalog.map((c) => c.id)).size).toBe(25);
    expect(catalog.every((c) => !("result" in c))).toBe(true);
  });
});
