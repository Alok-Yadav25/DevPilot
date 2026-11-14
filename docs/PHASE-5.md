# Phase 5 — live verification preparation (not complete)

Changed: `docs/VERIFICATION.md` lists all 12 requested real scenarios as not run, with provisioning, restart and evidence instructions. `scripts/verify_live.py` drives the real API and writes redacted observations; decisions are explicit. `test_live_pipeline.py` is opt-in and marked live, excluded from default pytest. `actions_inner.py` and its workflow generator add a host-acknowledged network disconnect before pytest, and a 120-second test deadline. Actions dispatch no longer sends an undocumented input (checked against current official REST docs).

Verified live: none. Owner confirmed key rotation; no provider revocation check was performed. Sandbox/target tokens, sandbox repo and target allowlist are absent locally. No repository was created, PR opened or service deployed. Dependencies still require network access during preparation; test execution is disconnected. This limitation is explicit in VERIFICATION.md.

Tests: mocked Actions tests and static workflow guard checks are local. The new live test has not run. Phase 5's real-service done condition is not met. Subsequent independent UI/replay/evaluation tooling can be prepared, but their live acceptance criteria remain unfulfilled.
