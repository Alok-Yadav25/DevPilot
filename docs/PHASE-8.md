# Phase 8 — practical review tools

Changed: NewRun offers an explicit repository readiness check using the shared policy endpoint and discards stale success for a changed URL. FailureExplanation reports what failed, attempts/baseline evidence and a specific next step. ReviewChecklist shows scope, test evidence, protected-file checks and remaining risks. Tests can compare attempt patches with resolved/remaining failures. The authenticated JSON report endpoint includes pinned SHA/model (when recorded), events, diff, test evidence and exact approval digest/decision events; frontend reports label playback provenance.

Tests: three frontend review/comparison regression tests and an in-process authenticated report/approval-record test. Frontend: 26 passed; focused API: 18 passed; production build, typing and typography checks passed. Checks use fixtures/mocked API responses, not live providers.

Verified live: none. Phases 5/6 live criteria remain pending missing GitHub configuration. These tools are implemented in phase order but do not certify the underlying real-service pipeline. No extra dashboard, deployment or animation feature added.
