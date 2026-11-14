# Phase 3 — shared policy and token boundaries

Changed: `app/policy.py` checks strict GitHub URLs, allowlist/configured owner, anonymous public metadata, repo size, checked-out file count, Python 3.11 metadata, dependency manifests and presence of pytest-style tests. API readiness/start, worker start, CLI, agent clone/recovery and patch retries call the shared gate. Source searches remain local. `service.py` now uses only TARGET_GITHUB_TOKEN for approved publication; the Actions factory passes only SANDBOX_GITHUB_TOKEN. Issue reads are anonymous. Sandbox workflow supports the same owner/allowlist settings. `.env.example` documents the active settings without keys.

Tests added: table-driven mocked public/private/URL/size/language/allowlist/injection cases, local checkout/file-count/attempt/Python-version tests, mocked target-publication credential isolation. Default suite: 143 passed, 5 local-container integration tests skipped. Ruff/mypy pass.

Verified live: none. Repository readiness uses an anonymous GitHub request (lower account-independent rate budget), followed by a bounded temporary clone. It never uses a target or sandbox write token for retrieval. Private repos return a public-repository error. Actual repo/PAT permissions and sandbox repository variable configuration remain unverified.

Risks: GitHub metadata can become stale; the worker and retry path check it again. Dependency install/test compatibility can only be established by the sandbox, not by a readiness scan. No external writes or deployment performed. Manual Groq revocation is still unconfirmed.
