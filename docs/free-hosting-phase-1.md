> Historical checkpoint. For the current implementation and measured checks, see [README](../README.md), [quality evidence](quality/REPORT.md) and [live verification](VERIFICATION.md).

# Free-hosting revision — Phase 1

This revision implements only the CLI/agent sandbox transport. It does not deploy anything. ChatGPT hosting is prohibited. The existing web/API implementation is retained; migration of those services to Actions, Neon checkpoints and real replay storage belongs to later review phases.

## Set up the sandbox repository

1. Create a **public** GitHub repository you own named `devpilot-sandbox`. Do not add repository secrets.
2. Copy `sandbox-repo/.github/workflows/run-tests.yml` into its default branch. The separate repo needs only that workflow. No upload or repo creation is performed automatically by this build.
3. Set the repository variable `ALLOWED_TARGET_REPOS` to a comma-separated list of public repositories you own or have reviewed. Also configure the same list on the backend. Empty means deny all.
4. Create a fine-grained PAT scoped only to this sandbox repository, with **Actions: write** and **Contents: write**. Put it in your backend's ignored `.env` as `SANDBOX_GITHUB_TOKEN`, never in the workflow.
5. Set `SANDBOX_REPO=your-user/devpilot-sandbox` and `RUNNER_MODE=github_actions`. The default branch is `main`; set `SANDBOX_DEFAULT_BRANCH` if different.
6. Put your Groq key in `.env`, set `GROQ_MODEL`, and run `uv run devpilot doctor`.

```sh
uv run devpilot run https://github.com/YOUR_USER/YOUR_PUBLIC_REPO \
  --issue 'Describe the reproducible bug' \
  --expected-failure 'tests/test_example.py::test_regression' --json-events
```

The CLI clones without credentials and caps repository size at 50 MiB. It submits an empty baseline patch twice, then each locally validated candidate at the exact cloned commit SHA. Each call creates a unique `patch/<job-id>` branch **only in the sandbox repository**, requests a dispatch run ID, polls at six-second intervals, downloads the named artifact, and removes its patch branch in `finally`. It never pushes to the target repo or opens a PR. Human-approved target publication remains a separate later phase.

The sandbox repository is public: patches, workflow logs and artifacts must be treated as public. Never submit private code or secrets. The backend rejects known secret-like patch content and only allowlisted public target repositories are accepted.

## Why the workflow differs from the supplied reference

- Empty baselines skip `git apply`, so they are valid no-ops.
- It fetches the immutable tested commit, not a moving branch.
- A matching, relevant failing baseline is necessary to repair a bug. Unrelated failures or different results across the two baselines stop as unsuitable. An already-green suite needs a regression test first.
- `actions/checkout` uses `persist-credentials: false`. The job has only `contents: read`; the dispatch PAT and Groq key never enter it.
- Untrusted target code runs in a **separate, network-enabled Docker container inside the Actions VM**, not on the credential-bearing Actions host. Render does not run Docker. The container has no host mounts or credential environment, a read-only root, a non-root UID, resource limits, and a 300-second watchdog. Dependencies may download in this Actions mode; local Docker remains networkless.
- The trusted image is built before any target code runs. `pip`, build hooks, git checkout and pytest execute only inside the container. The template is generated from `sandbox-image/actions_inner.py` by `scripts/build_actions_workflow.py`; publish only its generated YAML.
- The report records test IDs/outcomes, failure details and logs. The agent can compare baseline consistency and reject disappearing/skipped tests. Reports are evidence, not tamper-proof attestations.
- Artifacts have one-day retention, a 2 MB expanded/download limit, and bounded log tails. Missing artifacts are retried once. Failed setup, malformed results, cancellations and timeouts stop honestly.

Standard GitHub-hosted runners in public repos are free. Artifact storage has separate allowances; do not assume unlimited storage. Keep the repository public, use the standard `ubuntu-latest` runner, and configure a zero-dollar spending budget on GitHub. See [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions). Dispatch `return_run_details` is supported by [the current workflow API](https://docs.github.com/en/rest/actions/workflows).

A queue wait counts toward the CLI's global deadline. Free runner queue delays and Groq throttling can make a run time out. The workflow serializes this sandbox repo's jobs; backend concurrency is a later phase. Cancel/cleanup requests have a separate short timeout, and cleanup failures are surfaced for manual attention. A process crash before receiving a dispatch response can leave a branch or job; inspect Actions before retrying. No mutation is blindly retried after an ambiguous network failure.

## Local mode and replay

`RUNNER_MODE=docker` selects the existing local, networkless Docker runner. The revised CLI still enforces the target allowlist and public-only cloning. `RUNNER_MODE=replay` refuses live CLI repairs; it does not manufacture test evidence. Real recorded replay transport/API work belongs to Phase 6, and the current browser walkthroughs remain labeled scripted illustrations.

## Verification

Unit tests use HTTP mocks, not remote workflow runs. They cover successful empty baselines, strict repository/ref validation, allowlist enforcement, artifact handling, cancellation/timeout cleanup and the workflow's credential boundary. Existing clone and patch-validator tests are retained.

**Live verification on three owned public repositories has not run**: the environment has no configured sandbox repository or scoped sandbox token. The three existing `examples/` fixtures can be published by their owner and tested with this CLI once those prerequisites exist. No success rate is claimed.

Measured checks: **110 tests passed, 5 real Docker checks skipped**. Ruff and mypy pass. Generated workflow YAML, embedded Python and bash syntax checks pass. Live GitHub Actions execution is unverified.

Phase 1 stops here for review. Postgres checkpointer migration, API changes, PR flow migration, UI cold-start states, real replays and Vercel/Render/Neon deployment have not been performed in this revision.
