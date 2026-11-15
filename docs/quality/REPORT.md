# Local quality evidence — November 15, 2026

These results describe local code and browser checks. **No real GitHub/Groq repair, live restart test or hosted deployment is certified.** The owner confirmed key rotation; revocation was not independently checked.

## Check results

| Check | Observed result | Scope |
| --- | --- | --- |
| Backend default pytest | 152 passed, 5 skipped, 1 live test deselected | Local unit/controller/in-process checks; provider HTTP and model/test outcomes are mocked |
| Ruff / mypy | Passed; 44 app source files type-checked | Local static checks |
| Frontend tests | 42 passed | Vitest 5.1.0; fixtures, mocked fetch and fake timers |
| Frontend production build | Passed | React 18 / Vite 6 |
| Typography check | Passed | No authored text sizes below 12px |
| Playwright | 11 passed, 1 mobile-only test skipped on desktop | Desktop 1440×900 and mobile 390×844; mocked API, fixture playback, approval, navigation, theme, worker failures and mobile focus |
| SQLite migrations | Upgrade through 0004 passed | Local migration smoke check; Postgres has not been tested live |
| Gitleaks | 0 findings in available root/frontend refs and a 184-file working-source snapshot | Redacted local scans; ignored environments excluded; no remote refs fetched |
| npm application dependency audit | 0 reported vulnerabilities | After removing optional Lighthouse dependencies from the application tree |
| Evaluation preparation | 25 deliberately buggy Git fixtures materialized locally | No fixture code executed on the host; none published or evaluated through real providers |

The API-to-Actions integration test uses the actual service, factory, adapter, agent, temporary Git checkout, patch validator and database, with **mocked GitHub HTTP and scripted Groq/test outcomes**. It observes two baseline jobs and one patched job, stores replay evidence, and stops for approval without target publication. It is not an autonomous repair success measurement.

Additional regressions cover node-boundary power loss (including retry), lease expiry/terminal preservation, remote reattachment without a second dispatch, lost PR-response reconciliation, idempotent run creation (including simultaneous retries), slow readiness without duplicate mutation, redacted logs/errors, cancellation cleanup before target-policy checks, old-schema health failure and approval-bound report export.

## Lighthouse

A later minimal-workspace snapshot records 100/99/99 performance and 100 accessibility across three trials per route. Its scope, timing and remaining limitations are documented in [UI polish report](../UI-POLISH.md), with [separate raw reports](polish-lighthouse/summary.json). The table below retains the earlier measurements.

Actual local Lighthouse 10.1.1 measurements using Chrome 157, the desktop preset, a persistent warm browser profile and a production static build with a mocked API. The run route uses an **illustrative sample**; history includes that local sample. These are not hosted, mobile, cold-cache, cold-server or real-provider measurements. The older audit version limits comparison with current Lighthouse releases and does not replace manual screen-reader testing.

| Page | Performance trials | Median | Accessibility trials |
| --- | --- | --- | --- |
| Overview | 99, 99, 99 | 99 | 100, 100, 100 |
| Run workspace | 97, 98, 98 | 98 | 100, 100, 100 |
| History | 98, 99, 99 | 99 | 100, 100, 100 |

All nine raw reports and the machine-readable summary are in [lighthouse/](lighthouse/summary.json). Earlier measurements are retained under [initial-pass](lighthouse/initial-pass/summary.json), including a 58 performance result and a heading-order finding. The initial report recorded a long unattributable browser task; its root cause was not established. Subsequent trials were retained together rather than selecting a best score. Missing switch labels and heading order were fixed. Scores vary by device, tool version, cache and load; no production guarantee is implied.

Lighthouse's older browser-download dependency chain had npm advisories. It was removed from `frontend/package.json` and isolated in ignored local tooling, used only on trusted localhost pages with already installed Chrome. The application dependency audit reports zero findings; that does not certify the optional audit toolchain. See [frontend audit instructions](../../frontend/README.md).

## Accessibility and mobile limits

Browser checks cover readable text, no mobile horizontal page overflow, a visible Start control without initial scrolling, labelled switches/status updates, diff selection, review tabs and explicit keyboard approval. Reduced motion is configured. A full manual screen-reader audit, real touch-device inspection and hosted performance testing have not run. The workflow diagram is behind a tab and heavy diff/graph components are lazy-loaded.

## Live acceptance still pending

- Configure a public sandbox repository, separate scoped sandbox/target PATs and allowlisted owned public repos in the local environment.
- Run every scenario in [VERIFICATION.md](../VERIFICATION.md), including a real API process kill during an Actions wait and an approved real draft PR. Postgres lease contention, remote cleanup and proxy reconnect behavior still need real evidence.
- Produce at least two real recordings. Current real recordings: **0**.
- Publish and run the 25 evaluation fixtures through the real API pipeline. Current real results: **0**, repair success **unknown**. Failed cases must remain in the denominator. Legacy rows without provenance are excluded from measured repair metrics.
- Actions dependency preparation still has public network access. Test execution is disconnected and bounded in code; that boundary has not been exercised on a real Actions runner. Strict offline installation needs a prebuilt dependency image/wheelhouse.

Nothing was deployed, pushed remotely or hosted on ChatGPT/OpenAI services.
