# Real-service verification

Updated November 16, 2026. **One curated fixture completed a real dry run, including human approval.** The public website, hosted API, Groq, Neon and GitHub Actions were used without mocks. Two baselines reproduced the expected failure, the first patch passed both tests, AI review completed, the saved review survived an actual Render restart, and the owner approved the exact diff. No target branch or PR was created. This is not a benchmark success rate: there are zero executed evaluation cases. Groq key rotation was confirmed by the owner; revocation was not independently checked. See [deployment status](DEPLOYMENT.md) and the [redacted evidence record](evidence/hosted-slugify-2026-11-16.json).

| Scenario | Real result | Evidence | Date |
| --- | --- | --- | --- |
| First-attempt fix | Passed on one curated fixture after sandbox setup correction | [Patch tests](https://github.com/Alok-Yadav25/devpilot-sandbox/actions/runs/43749699405), [evidence](evidence/hosted-slugify-2026-11-16.json) | 2026-11-16 |
| Fix requiring retry | Not run | — | — |
| Failure after three attempts | Not run | — | — |
| Unrelated baseline failure → unsuitable | Not run | — | — |
| Patch does not apply | Not run | — | — |
| Cancel active Actions job | Not run | — | — |
| Reject at approval | Not run | — | — |
| Approve dry run | Passed; owner approved exact diff, API status completed, no PR | [Evidence](evidence/hosted-slugify-2026-11-16.json) | 2026-11-16 |
| Approve → real draft PR | Not run | — | — |
| Kill API during Actions wait, restart | Not run | — | — |
| Restart while awaiting approval | Passed via actual Render service restart; same diff/review and three remote IDs | [Evidence](evidence/hosted-slugify-2026-11-16.json) | 2026-11-16 |
| Real Groq 429 | Not run | — | — |
| Missing artifact / remote timeout | Not run | — | — |

## Live deployment smoke evidence

The actual public website connected using the worker credential, submitted the slugify fixture with dry run enabled, navigated to the live run page, and connected SSE. Run `50736919a2124a1a914f3220cd5a2d8b` cloned pinned SHA `b1558611e3cf2444adaced6c299040f73a65a825` successfully, then failed while preparing baseline 1. Sandbox-token reads of the target and main ref returned 200; no sandbox branch was recorded as created, and no Actions run was dispatched. The owner then corrected the sandbox token's repository selection and Contents/Actions write access. That failed attempt produced no LLM call, tested patch, approval or PR. It remains in history as a failure.

The next run, `53e3ded130ff4793bbd6abf72058dd4e`, completed on the same pinned SHA. [Baseline 1](https://github.com/Alok-Yadav25/devpilot-sandbox/actions/runs/43749564693) and [baseline 2](https://github.com/Alok-Yadav25/devpilot-sandbox/actions/runs/43749633114) each reported the separator test failing and the empty-input test passing. [Patched tests](https://github.com/Alok-Yadav25/devpilot-sandbox/actions/runs/43749699405) reported both passing. Investigation duration was 136.73 seconds, excluding the human approval wait. Groq model: `openai/gpt-oss-120b`; one source line changed, no tests changed. Render recorded service restart event `evt-dbt02jrbc2fs73co00pg`; the API restored the same review and remote test IDs before recording the owner's dry-run approval. The target repository still had only `main` and zero PRs, and temporary sandbox branches were cleaned.

This verifies the approval-wait restart only. Restart during active Actions polling, all other node boundaries, PR publication and broad repair reliability remain unverified. One real recording is stored in Postgres; two recordings are required to complete the original replay phase.

The earlier shared-IP metadata limit blocked a request before run creation; the bounded anonymous-clone fallback was then deployed in commit `3ca1400`. Neither failure is an autonomous repair success.

## Provisioning checklist

1. Create a public repository you own named `devpilot-sandbox`. Copy `sandbox-repo/.github/workflows/run-tests.yml` onto its default branch. Set Actions repository variables `ALLOWED_TARGET_REPOS` and optionally `ALLOWED_TARGET_OWNER`, matching the API's values. Enable Actions. The owner approved creation, and `Alok-Yadav25/devpilot-sandbox` is now published.
2. Publish copies of `examples/slugify`, `examples/clamp` and `examples/backoff` to three small public repos you own. Preserve their known failing tests. Add those repo names to the allowlists. The three `Alok-Yadav25/devpilot-example-*` repositories are now published; their publication is not repair evidence.
3. Set separate fine-grained tokens locally: sandbox PAT limited to the sandbox repo (Actions write, Contents write), target PAT limited to the target repos (Contents write, Pull requests write). Never place either in the workflow or browser. Configure Groq, pooled Postgres, API access token and explicit CORS allowlist.
4. Run `alembic upgrade head`, start the API, and inspect `/api/health` and `/api/limits`. Set `GROQ_KEY_ROTATION_CONFIRMED=1` only after revocation. The model is configured by `GROQ_MODEL`; the current [Groq model list](https://console.groq.com/docs/models) includes the default `openai/gpt-oss-120b` as checked November 14, 2026. Account availability is checked at runtime.

## Evidence driver

```sh
GROQ_KEY_ROTATION_CONFIRMED=1 python scripts/verify_live.py \
  --repo https://github.com/YOUR_ACCOUNT/YOUR_BUG_REPO \
  --issue 'Describe the known bug' --decision none \
  --output .devpilot/verification/first-attempt.json
```

The default leaves the run waiting for human review. Inspect the diff/evidence in the website before approving. For an operator-authorized scripted decision, use `--decision approve_dry`, `reject`, `cancel` or `draft_pr`. **`draft_pr` explicitly authorizes a real new branch and draft PR**; it never merges. The script records actual API run data and duration; failed outcomes stay failed. It does not force a real model into a first-attempt/retry outcome or induce a provider's real rate limit. Do not present mocked 429 tests as a real quota event.

For each scenario, retain the JSON, API run ID, remote Actions URL(s) from run evidence, pinned SHA, PR URL if any and duration. Link redacted evidence in the table with the actual execution date. The opt-in pytest driver is `DEVPILOT_RUN_LIVE=1 pytest -m live backend/tests/test_live_pipeline.py` with `LIVE_API_URL`, `LIVE_REPO`, `LIVE_ISSUE` set. Default tests exclude it.

For restart evidence: start a real run; record the current remote Actions ID; stop the API process while that job is queued/running; restart against the same database; confirm the API polls that same ID and makes no second dispatch. Repeat after each completed node and during approval wait. Record process timestamps and remote URLs. Local simulations do not satisfy this requirement.

## Sandbox limitation

The Actions workflow prepares dependencies inside a restricted, secret-free container with public download access. Before importing pytest or executing test hooks, the trusted host disconnects its network, checks that no network remains, and acknowledges the test phase. The test phase has a 120-second timeout. **Dependency installation is not offline.** Repos requiring install-time network denial need a prebuilt offline dependency image/wheelhouse (the local runner supports that model); they are not certified by this Actions workflow. Network isolation and hard limits have not yet been exercised on a real Actions runner.

[GitHub's workflow API documentation](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event) was checked: API version 2026-03-10 returns the dispatch run ID/URLs. No undocumented `return_run_details` input is sent.
