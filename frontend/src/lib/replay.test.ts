import { describe, expect, it, vi } from "vitest";
import { advanceSample, makeSample } from "./examples";
import { advanceRecorded, makeRecorded } from "./replay";
function fixtureRecord() {
  let sample = makeSample("slugify");
  for (let i = 0; i < 20; i++) sample = advanceSample(sample);
  return {
    ...sample,
    id: "mocked-record",
    mode: "live" as const,
    test_evidence: [
      {
        job_id: "fixture",
        run_id: 42,
        status: "completed",
        url: "https://github.com/fixture/sandbox/actions/runs/42",
      },
    ],
  };
}
describe("recorded playback with fixture evidence", () => {
  it("preserves original events, patch and evidence without network calls", () => {
    const network = vi.spyOn(globalThis, "fetch");
    const source = fixtureRecord();
    const before = JSON.stringify(source);
    const playback = makeRecorded(source);
    const finished = advanceRecorded(playback, Date.now() + 86400000);
    expect(finished.status).toBe("ready_for_review");
    expect(finished.final_diff).toBe(source.final_diff);
    expect(finished.events).toEqual(source.events);
    expect(finished.test_evidence).toEqual(source.test_evidence);
    expect(JSON.stringify(source)).toBe(before);
    expect(network).not.toHaveBeenCalled();
    network.mockRestore();
  });
  it("refuses missing provenance and respects pause", () => {
    expect(() => makeRecorded(makeSample("clamp"))).toThrow(/evidence/);
    const playback = { ...makeRecorded(fixtureRecord()), paused: true };
    expect(advanceRecorded(playback, Date.now() + 10000).cursor).toBe(0);
  });
});
