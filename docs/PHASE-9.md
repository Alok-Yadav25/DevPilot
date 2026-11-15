# Phase 9 — quality evidence and evaluation tooling (live criteria incomplete)

Changed:

- `scripts/prepare_evaluation.py`: materialize 25 injected-bug Git fixtures locally, with an empty-URL publication manifest and pinned SHAs; no host execution or upload.
- `scripts/evaluate.py`: replace the old direct local-runner evaluation path with the real website/API pipeline; record attempts, duration, model, commit, failure reason and remote evidence without approval/publication.
- `db/models.py`, migration `0004_eval_evidence`, `api/eval.py`: persist provenance and failure reasons; exclude unproven legacy rows from measured repair metrics.
- `api/health.py`, `service.py`, `sandbox/base.py`, `agent/llm.py`: detect missing schema, clean cancelled remote jobs before target policy, expose observed wait budgets and use one graph runner protocol.
- `backend/tests/test_website_pipeline.py`, API regressions: exercise API-to-Actions with mocked providers; cover cancellation cleanup, report evidence and old-schema health.
- Frontend Playwright config/tests: desktop/mobile replay, patch review, explicit keyboard approval, readable text and viewport checks. These use mocked API data.
- Frontend review/status/evaluation labels: accessible switch names and heading order, keyboard tab navigation, distinct replay labels, and repair metrics hidden until real evidence.
- Frontend dependency files: add Playwright, update Vitest to address its critical audit finding, isolate Lighthouse outside application dependencies; npm reports zero application findings.
- `scripts/lighthouse.mjs`, `docs/quality/`: reproducible local measurement script, all three trials per page, initial lower results and explicit measurement limits.
- README and historical-note labels: current setup, runner/network boundaries, hosting ban and unmet live criteria.

Tests: 152 backend passed, 5 Docker checks skipped and 1 live test excluded. 27 frontend tests passed; 6 Playwright checks passed; build, Ruff, mypy, typography and SQLite migration checks passed. See [quality evidence](quality/REPORT.md) for actual Lighthouse trials and limitations.

Verified live providers: none. 25 local evaluation repos prepared; no real evaluation outcomes recorded. No real recordings or hosted scores are invented. Full live acceptance remains pending the missing GitHub configuration and actual scenario execution. No deployment or remote publication performed.

Repository preservation: the root initially had no committed application baseline and the frontend had separate local Git history. A final source-preservation commit tracks the complete existing application (including plain frontend files, not a broken Git link), retaining the nested local history. Ignored environments, dependencies, build output, local audit tools and obsolete ChatGPT hosting configuration are excluded. Generated Lighthouse evidence is marked as generated for review; secret scanning still includes it.

Final connection regression: run creation probes lightweight health before its longer readiness request; simultaneous idempotent retries are serialized with a database transaction lock and return one durable run. A fake-timer 55-second readiness test and a concurrent API retry test cover the regression.
