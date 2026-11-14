# Phase 1 — selected runner

Changed: `sandbox/factory.py` selects the existing Actions transport, local container runner, or non-executing replay runner. API/service/CLI now use the factory. Startup refuses missing Actions configuration, shared tokens, or a production local-container runner. Health checks the selected runner; limits expose local active/queued counts and query GitHub's workflow queue. API no longer refuses a run just because a worker slot is occupied (bounded queue).

Tests added: six mocked/local factory tests in `backend/tests/test_runner_factory.py`; updated in-process API health expectations. Existing Actions and container tests retained. Focused runner/API suites: 42 passed. Ruff and mypy pass.

Verified live: none. GitHub workflow availability/permissions, remote queue counts and website-to-Actions execution remain unverified without provisioned services. Replay cannot fabricate a test result; recorded-run playback comes in Phase 6. Provider budgets stay null until observed. No Docker SDK imports remain outside the local runner and its tests; runner selection necessarily retains configuration strings/import of the runner class.

Risks: manual Groq rotation remains unconfirmed. Durable recovery and a shared policy gate are next. No deployment or push performed.
