# Deployment status

Updated November 16, 2026 (India time). Source: [Alok-Yadav25/DevPilot](https://github.com/Alok-Yadav25/DevPilot). No ChatGPT/OpenAI hosting is used.

## Online services

| Component | Deployment | Verified state |
| --- | --- | --- |
| Frontend | [Cloudflare Pages](https://devpilot-alokyadav25.pages.dev) | Static React application, HTTPS and SPA routing |
| API | [Render API](https://devpilot-api-alok-yadav25.onrender.com) | Free plan, Singapore; **replay mode**, live execution disabled |
| Database | Neon project `restless-shadow-39597218` | Free organization, Singapore; pooled SSL connection, migration `0004_eval_evidence`, seven public tables |

The frontend is built with `VITE_API_URL=https://devpilot-api-alok-yadav25.onrender.com`. Provider credentials are never frontend variables. `render.yaml` is the **live-runner template**; it does not describe the temporary replay setting on the currently hosted service.

## Real hosting checks

These checks reached actual deployed services, not mocks. They do **not** verify autonomous repairs.

| Check | Observed result |
| --- | --- |
| Render deployment `dep-dbsvk2e1egvs73f0kgpg` | Live; API source `ebc1dd71e56ed162db253dba702d49f6e5369673` |
| `GET /api/health` | 200; database reachable, runner `replay`, ready for replay |
| `GET /api/health?lightweight=true` | 200; awake |
| `GET /api/runs` without credential | 401 |
| Authenticated runs, limits and evaluation | 200 |
| Public recordings | 200; **zero recordings** |
| Frontend-origin preflight | 200; exact Cloudflare origin allowed |
| Untrusted-origin preflight | 400; no allowed-origin response header |

HTTP evidence was collected at `2026-11-15T18:31:58Z` (November 16 in India). Private operator evidence is stored under ignored `.devpilot/deploy/`; credentials and database URLs are not published.

## Access and updates

1. Open the [workspace](https://devpilot-alokyadav25.pages.dev/workspace). Illustrative examples require no token.
2. For protected API data, open **Connect worker**. Use the API address above and `API_ACCESS_TOKEN` from this project's ignored local `.env`, or the Render service's private environment settings. This randomly generated worker token is **different from the Render API key**.
3. Click **Test & save**. Browser credentials are session-only. Replay mode refuses live repair requests even with valid access.

Cloudflare uses **Direct Upload**, not automatic GitHub deployment. After source changes, build with `VITE_API_URL` set and upload `frontend/dist` to the existing Pages project using authenticated Wrangler. No secrets belong in that directory. A persisted-state migration moves returning visitors with the old empty API address onto the bundled hosted address; custom worker addresses are preserved.

Render autodeploy is off. Trusted `app.serve` validates settings, runs Alembic migrations and starts one API process on Render's `PORT`. Migration failure prevents startup. The API image packages trusted backend code using Docker; the hosted API does not run a Docker test daemon.

## Published sandbox fixtures

The owner explicitly approved these public repositories and the exact three-repository sandbox allowlist. All four were created and their source pushed:

- [Sandbox workflow](https://github.com/Alok-Yadav25/devpilot-sandbox/blob/main/.github/workflows/run-tests.yml)
- [Slugify fixture](https://github.com/Alok-Yadav25/devpilot-example-slugify)
- [Clamp fixture](https://github.com/Alok-Yadav25/devpilot-example-clamp)
- [Backoff fixture](https://github.com/Alok-Yadav25/devpilot-example-backoff)

The workflow is dispatch-only. Publishing fixtures is not a test execution or repair success. No workflow dispatch was performed during provisioning.

## Remaining live-run setup

The separate `SANDBOX_GITHUB_TOKEN` and `TARGET_GITHUB_TOKEN` were **not found** in the project `.env` or Render when checked. The owner has been given token creation instructions. Before enabling live repairs:

1. Configure two distinct fine-grained tokens: sandbox-only Actions/Contents write, and target-only Contents/Pull requests write. Never reuse the broad GitHub CLI credential.
2. Privately set Groq and both GitHub tokens on Render. Set `SANDBOX_REPO`, an exact target allowlist, and `RUNNER_MODE=github_actions`; redeploy.
3. Check runner health, then execute the [real-service verification checklist](VERIFICATION.md). A complete GitHub/Groq repair, restart during Actions execution, approval and draft PR remain unverified. There are zero executed real evaluation cases and zero real replay records.

## Free-tier limits

These resources use free plans; no paid plan or paid fallback was selected. Usage remains subject to provider quotas. [Render Free](https://render.com/docs/free) sleeps after 15 minutes without inbound traffic and can take about a minute to wake. Its 750 monthly free instance hours are **shared across the workspace**, which already contains another service. Exhaustion can suspend services. Bandwidth/build overages can be billed if the account has a payment method; otherwise services/builds can be suspended. This deployment did not change account billing settings.

The client has bounded cold-start retries, but an actual idle sleep/wake cycle has not yet been measured on this deployment. Ephemeral API files are not durable; Postgres stores durable state. [Cloudflare Pages limits](https://developers.cloudflare.com/pages/platform/limits/) and Neon/Groq/GitHub quotas still apply. This is a public demonstration deployment, not an uptime guarantee.

## Local checks

Backend preparation: 160 passed, five optional Docker checks skipped, one live test excluded; Ruff and mypy pass. Frontend: 45 tests pass, including three mocked persisted-connection migration checks; production TypeScript/Vite build passes. Local/mock checks are distinct from the hosting checks above.
