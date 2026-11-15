# Real-service verification

Updated November 16, 2026. **No successful complete real repair has been verified.** A local passing mocked test is not an entry in this table. Groq key rotation was confirmed by the owner in chat; revocation was not independently checked. The hosted website, GitHub Actions API and Neon database are online; see [deployment evidence](DEPLOYMENT.md). The sandbox and three fixture repos have been published with an exact allowlist. Separate runtime PATs and Groq are now configured, and runner health passes. A first hosted dry run reached baseline preparation and failed with sandbox HTTP 403 before any Actions workflow was dispatched.

| Scenario | Real result | Evidence | Date |
| --- | --- | --- | --- |
| First-attempt fix | Blocked before tests: sandbox branch preparation denied (403) | [Hosted run](https://devpilot-alokyadav25.pages.dev/run/50736919a2124a1a914f3220cd5a2d8b) | 2026-11-16 |
| Fix requiring retry | Not run | — | — |
| Failure after three attempts | Not run | — | — |
| Unrelated baseline failure → unsuitable | Not run | — | — |
| Patch does not apply | Not run | — | — |
| Cancel active Actions job | Not run | — | — |
| Reject at approval | Not run | — | — |
| Approve dry run | Not run | — | — |
| Approve → real draft PR | Not run | — | — |
| Kill API during Actions wait, restart | Not run | — | — |
| Real Groq 429 | Not run | — | — |
| Missing artifact / remote timeout | Not run | — | — |

## Live deployment smoke evidence

The actual public website connected using the worker credential, submitted the slugify fixture with dry run enabled, navigated to the live run page, and connected SSE. Run `50736919a2124a1a914f3220cd5a2d8b` cloned pinned SHA `b1558611e3cf2444adaced6c299040f73a65a825` successfully, then failed while preparing baseline 1. Sandbox-token reads of the target and main ref returned 200; no sandbox branch was recorded as created, and no Actions run was dispatched. The owner was asked to correct the sandbox token's repository selection and Contents/Actions write access. No LLM call, tested patch, approval or PR was produced.

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
