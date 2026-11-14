# Phase 6 — truthful metrics and recorded replay

Changed: `replay_runs` model/migration stores snapshots only after a reviewed, passing Actions-backed run with remote evidence. Read-only replay endpoints and ReplayRunner load those records without provider calls. Frontend playback preserves original ordered events, diff, review and evidence, and simulates no model/test result. Overview distinguishes real recordings from illustrative examples, hides empty statistics, and labels approval rate as approvals among loaded live runs (not repair success). Publication failures after approval still count as approved.

Tests: mocked/in-process replay provenance/idempotent storage and provider isolation; two frontend fixture-record playback tests (not real recording evidence). Frontend: 21 passed; production build passed. Focused API/factory: 23 passed. Ruff/mypy and SQLite migrations pass.

Verified live: none. **Real recordings available: zero.** Two real successful recordings cannot be manufactured from unit fixtures; the phase's two-recording live condition remains unmet. Repair success remains absent until actual evaluation execution. Replay mode refuses live execution rather than calling a model under a demo label.

Risks/next: real recordings require configured services and successful reviewed runs. Playback is local and its decisions cannot publish the original patch. Calmer UI follows. No deployment or remote write performed.
