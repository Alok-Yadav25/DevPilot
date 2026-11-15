# Deployment status

Updated November 16, 2026 (India time). Source: [Alok-Yadav25/DevPilot](https://github.com/Alok-Yadav25/DevPilot). No ChatGPT/OpenAI hosting is used.

## Online services

| Component | Deployment | Verified state |
| --- | --- | --- |
| Frontend | [Cloudflare Pages](https://devpilot-alokyadav25.pages.dev) | Static React application, HTTPS and SPA routing |
| API | [Render API](https://devpilot-api-alok-yadav25.onrender.com) | Free plan, Singapore; **GitHub Actions** runner, separate tokens configured |
| Database | Neon project `restless-shadow-39597218` | Free organization, Singapore; pooled SSL connection, migration `0004_eval_evidence`, seven public tables |

The frontend is built with `VITE_API_URL=https://devpilot-api-alok-yadav25.onrender.com`. Provider credentials are never frontend variables. `render.yaml` describes the GitHub Actions runner; its initial replay-only deployment has been replaced by the configured live runner.

## Real hosting checks

These checks reached actual deployed services, not mocks. The infrastructure checks below are separate from the real dry-run repair documented in [VERIFICATION.md](VERIFICATION.md).

| Check | Observed result |
| --- | --- |
| Render deployment `dep-dbsvk2e1egvs73f0kgpg` | Live; API source `ebc1dd71e56ed162db253dba702d49f6e5369673` |
| `GET /api/health` | Initially 200 with runner `replay`; now 200 with runner `github_actions`, database/runner/Groq configuration ready |
| `GET /api/health?lightweight=true` | 200; awake |
| `GET /api/runs` without credential | 401 |
| Authenticated runs, limits and evaluation | 200 |
| Public recordings | 200; **one real recording**, created from the tested slugify run |
| Frontend-origin preflight | 200; exact Cloudflare origin allowed |
| Untrusted-origin preflight | 400; no allowed-origin response header |
| Live desktop and mobile browser smoke | Landing, workspace, real API health, illustrative demo and Diff tab pass; no horizontal overflow or JavaScript runtime errors |
| Returning visitor with old empty worker address | Automatically uses deployed API; saved theme preserved |

Frontend deployment [78098d2e](https://78098d2e.devpilot-alokyadav25.pages.dev) uses source `8ab0e8bb94e156bc7d859ee8e752aabbbd1ca61d`. Its [GitHub secret scan](https://github.com/Alok-Yadav25/DevPilot/actions/runs/43747669761) passed. Browser checks used a separate headless browser against the real public frontend and API, without mocked responses. The demo remains explicitly illustrative; it is not a repair test.

HTTP evidence was collected at `2026-11-15T18:31:58Z` (November 16 in India). Private operator evidence is stored under ignored `.devpilot/deploy/`; credentials and database URLs are not published.

## Access and updates

1. Open the [workspace](https://devpilot-alokyadav25.pages.dev/workspace). Illustrative examples require no token.
2. For protected API data, open **Connect worker**. Use the API address above and `API_ACCESS_TOKEN` from this project's ignored local `.env`, or the Render service's private environment settings. This randomly generated worker token is **different from the Render API key**.
3. Click **Test & save**. Browser credentials are session-only. Live requests use GitHub Actions; publication still requires approval of the exact tested diff.

Cloudflare uses **Direct Upload**, not automatic GitHub deployment. After source changes, build with `VITE_API_URL` set and upload `frontend/dist` to the existing Pages project using authenticated Wrangler. No secrets belong in that directory. A persisted-state migration moves returning visitors with the old empty API address onto the bundled hosted address; custom worker addresses are preserved.

Render autodeploy is off. Trusted `app.serve` validates settings, runs Alembic migrations and starts one API process on Render's `PORT`. Migration failure prevents startup. The API image packages trusted backend code using Docker; the hosted API does not run a Docker test daemon.

## Published sandbox fixtures

The owner explicitly approved these public repositories and the exact three-repository sandbox allowlist. All four were created and their source pushed:

- [Sandbox workflow](https://github.com/Alok-Yadav25/devpilot-sandbox/blob/main/.github/workflows/run-tests.yml)
- [Slugify fixture](https://github.com/Alok-Yadav25/devpilot-example-slugify)
- [Clamp fixture](https://github.com/Alok-Yadav25/devpilot-example-clamp)
- [Backoff fixture](https://github.com/Alok-Yadav25/devpilot-example-backoff)

The workflow is dispatch-only. Publishing fixtures is not a test execution or repair success. No workflow dispatch was performed during provisioning.

## Live verification and remaining work

The separate sandbox and target tokens are now configured privately on Render. Both authenticated as the expected GitHub owner; the sandbox workflow is active and reachable. A subsequent real workflow dispatch and patch test verified sandbox write/dispatch access. Target publication permissions remain unverified because no PR has been authorized.

1. Keep the two fine-grained tokens separate: sandbox-only Actions/Contents write, and target-only Contents/Pull requests write. The broad GitHub CLI credential is not used by the deployed application.
2. Groq, both GitHub tokens, `SANDBOX_REPO`, the exact three-repository allowlist, and `RUNNER_MODE=github_actions` are configured. Owner-wide access is disabled.
3. Check runner health, then execute the [real-service verification checklist](VERIFICATION.md). A real website dry run was accepted after the quota fix, but failed preparing the baseline branch with sandbox HTTP 403. After the owner corrected sandbox access, a second real website run passed both baselines, generated a first-attempt patch, passed both tests, completed AI review and human dry-run approval. The saved review survived an actual Render restart. No target branch or PR was created. There is one real replay record and zero executed evaluation cases. Restart during Actions execution, draft PR publication and the other live scenarios remain unverified.

## Shared GitHub quota regression

The first hosted run request was rejected before a run was created because Render's shared IP had exhausted the anonymous GitHub REST metadata quota. The fix uses an anonymous shallow clone with the existing size, file-count, timeout, Python and pytest checks when metadata returns 403/429. No scoped token is borrowed for policy metadata. Repository code is never executed by this check. Five mocked regressions cover quota fallback, inaccessible/private-style clone failure, size and setup rejection, plus temporary-directory cleanup. This fallback can require an extra clone; it is bounded rather than a free-tier quota bypass.

## Free-tier limits

These resources use free plans; no paid plan or paid fallback was selected. Usage remains subject to provider quotas. [Render Free](https://render.com/docs/free) sleeps after 15 minutes without inbound traffic and can take about a minute to wake. Its 750 monthly free instance hours are **shared across the workspace**, which already contains another service. Exhaustion can suspend services. Bandwidth/build overages can be billed if the account has a payment method; otherwise services/builds can be suspended. This deployment did not change account billing settings.

The client has bounded cold-start retries, but an actual idle sleep/wake cycle has not yet been measured on this deployment. Ephemeral API files are not durable; Postgres stores durable state. [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/) and Neon/Groq/GitHub quotas still apply. This is a public demonstration deployment, not an uptime guarantee.

## Local checks

Backend after deployment regression fixes: 166 passed, five optional Docker checks skipped, one live test excluded; Ruff and mypy pass. Frontend: 46 tests pass, including three mocked persisted-connection migration checks; production TypeScript/Vite build passes. A sixth mocked regression checks that sandbox permission errors identify the operation without exposing response secrets. Local/mock checks are distinct from the hosting checks above.

The final frontend polish distinguishes recorded runs from scripted samples in the playback confirmation and shows **Connect worker** when a healthy API only needs the browser credential. The recorded-playback confirmation regression uses mocked local state and confirms that playback approval never sends a POST.
