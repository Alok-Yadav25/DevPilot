# Workspace polish and issue audit

The subsequent [landing redesign](LANDING-REDESIGN.md) moves the form to `/workspace` and refreshes the visual theme. The report below records the earlier audit.

November 15, 2026. This is a local code/UI audit, not certification that every defect is resolved. Nothing was deployed or pushed remotely.

## Phase 7 follow-up report

### Changed

| Files | Reason |
| --- | --- |
| `frontend/src/components/Layout.tsx` | Remove workspace/profile/marketing clutter; collapse usage; fix mobile keyboard focus, Escape, background interaction and hidden navigation. |
| `frontend/src/pages/Home.tsx` | One prominent form; examples on demand; no empty recordings section or redundant metric line; distinguish loading and history errors. |
| `frontend/src/pages/NewRun.tsx` | Shorter labels; optional details collapsed; real multiline failing-test selectors; disable edits during submission; ignore stale readiness responses. |
| `frontend/src/pages/LiveRun.tsx` | Shorten repeated status text; isolate worker caches and requests; reconnect silent streams; correct completed progress count; keep the active step visible. |
| `frontend/src/pages/History.tsx` | Remove redundant summary cards and storage prose; keep filters and clear confirmation; show worker failures explicitly. |
| `frontend/src/pages/Evaluation.tsx` | Concise results explanation and collapsed methodology; show unavailable results honestly; disable export on fetch errors. |
| `frontend/src/pages/About.tsx` | Three short steps; essential safeguards; detailed requirements and limitations on demand. |
| `frontend/src/components/Examples.tsx` | Remove repetitive badges/footers while retaining illustrative labelling. |
| `frontend/src/components/ConnectionDialog.tsx` | Test candidates before saving; preserve a working connection on failure; allow cancellation; distinguish worker credentials from provider keys. |
| `frontend/src/lib/connection.ts` | Normalize worker addresses; reject unsafe URLs; authenticate the candidate independently. |
| `frontend/src/lib/api.ts`, `store.ts` | Scope private query caches to worker address and credential revision; capture each request's connection; keep the token in session storage. |
| `frontend/src/lib/client.ts`, `events.ts` | Cancel abandoned callers during wake-up; give readiness checks adequate time; resume SSE from the last event ID with an idle watchdog and polling fallback. |
| `frontend/src/components/RunReview.tsx` | Do not mark an absent diff as validated scope. |
| `frontend/src/components/AgentGraph.tsx` | Formatting only. |
| `frontend/src/styles/index.css` | Calmer spacing, readable text, responsive forms, compact timeline and correctly hidden mobile navigation. |
| `frontend/scripts/lighthouse.mjs`, frontend README | Allow separate audit snapshots without overwriting earlier evidence. |
| Root README | Remove an obsolete claim that the removed overview approval metric is still displayed. |

Approval confirmation, exact diff hashing, protected test files, honest illustrative/recorded labels, session-only worker credentials and the no-auto-merge rule remain in place.

### Tests added or updated

All provider responses below are **mocked**; these are not live GitHub/Groq tests.

- `connection.test.ts`: address normalization, five unsafe address cases, and credential preservation on a rejected candidate.
- `ConnectionDialog.test.tsx`: failed saves preserve settings/history, authenticated successful saves replace the cache, and closing an in-flight check cancels it without saving.
- `client.test.ts`: cancellation during shared wake-up does not retry an abandoned action or replace the UI state with an error.
- `events.test.ts`: dropped streams resume with Last-Event-ID, duplicate events are ignored, and silent streams reconnect after the heartbeat deadline.
- `worker-context.test.tsx`: a different worker's cached run cannot appear after switching connections; multiple failing tests are sent as separate selectors with dry run enabled.
- `workflows.test.tsx`: concise labels retain the existing approval and investigation safeguards.
- `e2e/workspace.spec.ts`: desktop/mobile form visibility, readable text and no page overflow; sample and recorded-fixture playback; explicit keyboard approval; correct completed progress; theme persistence; navigation/search; failed candidate saves; honest history/evaluation failures; mobile focus containment and Escape.

### Observed checks

| Check | Result | Scope |
| --- | --- | --- |
| Backend pytest | 152 passed, 5 skipped, 1 live test deselected | Default local suite; external provider behavior mocked. Docker integration skips require opt-in. |
| Ruff / mypy | Passed; 44 application source files | Local static checks. |
| Frontend Vitest | 42 passed | Fixtures, mocked fetch and fake timers. |
| Frontend production build | Passed | TypeScript and Vite. |
| Formatting / typography | Passed | No authored text below 12px. |
| Playwright | 11 passed, 1 skipped | Desktop 1440×900 / mobile 390×844, temporary Chrome profiles and mocked API. Desktop skips the mobile-only drawer test. |
| Gitleaks source scan | 0 findings | Redacted scan of the final frontend source; earlier full-history evidence remains in the quality report. |

Screenshots were visually inspected for the overview, diff workspace and mobile light theme. Generated browser artifacts stay local under `frontend/test-results/`.

### Performance snapshot

The layout/copy revision was measured locally with Lighthouse 10.1.1, a warm Chrome desktop profile, production build and mocked API. Three trials per route:

| Page | Performance | Accessibility |
| --- | --- | --- |
| Overview | 100, 100, 100 | 100, 100, 100 |
| Run workspace | 99, 99, 99 | 100, 100, 100 |
| History | 99, 99, 99 | 100, 100, 100 |

[Raw reports and summary](quality/polish-lighthouse/summary.json) are retained separately from earlier measurements. This snapshot preceded the final mobile focus and history-loading refinements; it is not a measurement of hosted performance, cold starts or a real repair. The older optional audit tool has known dependency advisories and remains isolated from application dependencies. A maintained Lighthouse release, real devices and manual screen-reader use are still needed before launch.

### Verified live

**None against external services.** Browser tests really ran locally, but API data and provider outcomes were mocked. No live-test success is inferred from those checks.

### Known gaps and next step

- A complete real GitHub/Groq repair, restart during a remote Actions job, cancellation cleanup, and approved draft PR still need evidence in [VERIFICATION.md](VERIFICATION.md).
- Postgres recovery/lease contention and deployed proxy reconnect behavior remain unverified against real infrastructure.
- Real recorded runs: zero verified. Real pipeline evaluation outcomes: zero. Repair success remains unknown; illustrative fixtures do not count.
- Actions dependency preparation uses public download access. Strict offline installation needs a prepared image/wheelhouse; real Actions isolation/resource enforcement remains unverified.
- Key rotation is owner-confirmed, not independently confirmed in the provider console. No keys were printed or changed during this UI pass.
- There was no deployment. ChatGPT/OpenAI hosting configuration remains absent. External hosting requires the owner's authorization.

The next acceptance step is configuring the owned sandbox/target repositories and separate scoped credentials locally, then running the real-service checklist. Further cosmetic changes cannot replace that evidence.
