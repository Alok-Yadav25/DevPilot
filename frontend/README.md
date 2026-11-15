# DevPilot frontend

React 18, TypeScript, Vite, Tailwind tokens, Radix controls, Framer Motion, React Flow, react-diff-view, TanStack Query, Zustand, Lucide and Sonner.

```sh
npm ci
npm run dev
npm test
npm run build
npm run check:typography
npm run test:e2e
```

Vite serves localhost and proxies `/api` to `127.0.0.1:8000`. Scripted examples work without services and stay labelled **Illustrative sample**. Real recordings retain events, diffs, reviews and Actions evidence; no real recordings are bundled. Replay decisions never publish a PR. Live repairs need the configured FastAPI worker, Postgres, Groq and separate sandbox/target GitHub tokens. Enter only the worker access token in the browser.

The landing page at `/` uses warm ivory, charcoal and champagne tones, Space Grotesk/Inter with Instrument Serif accents, a staggered hero reveal and an interactive illustrative preview. It makes no API requests. `/workspace` contains the focused overview. The supplied monogram is recreated as a scalable SVG and used for branding and the adaptive favicon; the linked Alok Yadav credit appears in both footers. The overview has one run form; examples are behind a button. Live Run uses a compact timeline and Activity/Diff/Tests/Review/Workflow tabs. The workflow graph loads on demand. Review readiness opens the diff; failures include evidence and next steps. Text sizes are at least 12px; reduced motion and desktop/mobile layouts are covered by local checks.

## Browser and audit checks

Playwright tests use mocked API responses and fixture recordings, not real-service evidence. Install Chromium with `npx playwright install chromium`, or set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` to an installed browser executable. Smoke tests cover desktop/mobile landing navigation, logo and credit links, preview tabs/autoplay/pause, reduced motion, visible text with real browser animation timing, patch inspection, workflow loading, replay and explicit keyboard approval.

Lighthouse is optional and isolated from application dependencies. The recorded local audits used version 10.1.1; its older browser-download dependency chain has known npm advisories, so it is not installed by `npm ci`. Only trusted localhost pages and an already installed Chrome were used. Use a maintained audit environment before a public launch. To reproduce that exact audit tool in an ignored local directory:

```sh
npm install --prefix ../.devpilot/quality-tools --no-save --ignore-scripts lighthouse@10.1.1
npm run build
PLAYWRIGHT_CHROMIUM_EXECUTABLE='/path/to/chrome' npm run audit:quality
```

`DEVPILOT_LIGHTHOUSE_MODULE` can select a different external Lighthouse module. Set `DEVPILOT_QUALITY_OUTPUT` to retain a separate audit snapshot. The script measures the landing, overview, run and history pages in three desktop trials per route against a local production build and mocked API. The run screen uses an illustrative fixture. Every trial is retained in `../docs/quality/lighthouse/`; the report states the version, scope and variability. This is not a hosted or real-provider benchmark.

See the [landing design/check report](../docs/LANDING-REDESIGN.md), parent [README](../README.md), [quality evidence](../docs/quality/REPORT.md) and [live verification checklist](../docs/VERIFICATION.md).

## Hosting policy

Never publish, synchronize or host this project on ChatGPT Sites or any ChatGPT/OpenAI hosting service. Keep it local unless the user explicitly authorizes another provider. Obsolete hosting configuration remains deleted.
